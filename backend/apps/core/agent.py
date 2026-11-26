"""Browser Use adapter. ORM access is exclusively in business services/worker."""

import asyncio, json, socket, tempfile, time
from pathlib import Path
from urllib.parse import urlsplit
from asgiref.sync import sync_to_async
from django.conf import settings
from pydantic import BaseModel, Field
from jsonschema import validate
from .security import validate_url, fingerprint, safe_url
from .network import GuardProxy


class Output(BaseModel):
    items: list[dict] = Field(min_length=1, max_length=1000)
    source_urls: list[str] = Field(min_length=1)


class ApprovalPending(Exception):
    pass


def validate_output(raw, schema, domains):
    result = Output.model_validate(raw)
    for url in result.source_urls:
        validate_url(url, domains)
    for row in result.items:
        if not row or any(v is None or v == "" for v in row.values()):
            raise ValueError("结果字段不完整")
    if schema:
        validate(result.model_dump(), schema)
    return result.model_dump()


class BrowserAgentService:
    def __init__(
        self,
        config,
        record,
        approval=None,
        request_approval=None,
        consume=None,
        llm=None,
    ):
        self.config = config
        self.record = record
        self.approval = approval
        self.request_approval = request_approval
        self.consume = consume
        self.allow_post = False
        self.pending = None
        self.observed = []
        self.saved = None
        self.artifact_count = 0
        self.llm = llm
        self.raw_result = ""
        self.usage = {}
        self.evidence = []
        self.screenshot_count = 0

    async def log(self, *args, **kwargs):
        await sync_to_async(self.record, thread_sensitive=True)(*args, **kwargs)

    async def run(self):
        from playwright.async_api import async_playwright

        if self.config["target_url"]:
            validate_url(self.config["target_url"], self.config["allowed_domains"])
        with (
            GuardProxy(self.config["allowed_domains"]) as proxy,
            tempfile.TemporaryDirectory(prefix="browserflow-") as profile,
        ):
            async with async_playwright() as p:
                with socket.socket() as sock:
                    sock.bind(("127.0.0.1", 0))
                    port = sock.getsockname()[1]
                context = await p.chromium.launch_persistent_context(
                    profile,
                    headless=True,
                    channel=settings.BROWSERFLOW_CHROMIUM_CHANNEL or None,
                    service_workers="block",
                    accept_downloads=False,
                    proxy={"server": proxy.url, "bypass": "<-loopback>"},
                    args=[
                        f"--remote-debugging-port={port}",
                        "--disable-quic",
                        "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                    ],
                )
                self.context = context

                async def gate(route):
                    req = route.request
                    try:
                        validate_url(req.url, self.config["allowed_domains"])
                        # Block automatic form submits, uploads, scripts' writes and arbitrary downloads.
                        demo = settings.DEMO_ORIGIN.rstrip("/") + "/api/applications"
                        if req.method not in ["GET", "HEAD"] and not (
                            self.allow_post and req.url == demo and req.method == "POST"
                        ):
                            raise ValueError("写入操作需要专用审批工具")
                        await route.continue_()
                    except Exception:
                        await route.abort("blockedbyclient")

                await context.route("**/*", gate)
                await context.route_web_socket("**/*", lambda route: route.close())
                self.page = context.pages[0]
                try:
                    if self.approval:
                        return await self.resume()
                    if self.config["model_name"] == "mock":
                        return await self.mock()
                    return await self.live(f"http://127.0.0.1:{port}")
                finally:
                    await context.close()

    async def navigate(self):
        start = time.monotonic()
        await self.page.goto(self.config["target_url"], wait_until="domcontentloaded")
        validate_url(self.page.url, self.config["allowed_domains"])
        await self.log(
            "navigate", {}, safe_url(self.page.url), time.monotonic() - start
        )

    async def snapshot(self):
        if self.screenshot_count >= 3:
            return ""
        self.screenshot_count += 1
        folder = Path(settings.MEDIA_ROOT) / str(self.config["run_id"])
        folder.mkdir(parents=True, exist_ok=True)
        phase = "approved" if self.approval else "prepare"
        path = folder / f"{phase}-{self.screenshot_count}.png"
        await self.page.screenshot(path=str(path))
        return str(path.relative_to(settings.MEDIA_ROOT))

    async def collect(self):
        # Independent DOM evidence: model-supplied rows must match observed page data.
        rows = await self.page.locator("[data-product]").evaluate_all(
            '(nodes)=>nodes.map(n=>({name:n.querySelector("[data-name]").textContent.trim(),price:n.querySelector("[data-price]").textContent.trim(),url:n.querySelector("a").href}))'
        )
        self.observed.extend(rows)
        self.evidence.append(
            {
                "url": self.page.url,
                "text": await self.page.locator("body").inner_text(),
                "links": await self.page.locator("a[href]").evaluate_all(
                    "(nodes)=>nodes.map(n=>n.href)"
                ),
            }
        )
        return rows

    async def prepare(self, fields: dict):
        if (
            not settings.ALLOW_DEMO
            or self.page.url != settings.DEMO_ORIGIN.rstrip("/") + "/form"
        ):
            raise ValueError("表单写入仅支持隔离的 Demo；其他网站需新增专用审批适配器")
        if set(fields) != {"applicant", "department", "reason"} or any(
            not isinstance(v, str) or not v.strip() or len(v) > 500
            for v in fields.values()
        ):
            raise ValueError("申请字段无效")
        for key, value in fields.items():
            await self.page.locator(f'[name="{key}"]').fill(value)
        actual = {
            key: await self.page.locator(f'[name="{key}"]').input_value()
            for key in fields
        }
        payload = {
            "url": self.page.url,
            "fields": actual,
            "form_version": await self.page.locator("form").get_attribute(
                "data-version"
            ),
        }
        await self.log(
            "prepare_form",
            {"fields": actual},
            safe_url(self.page.url),
            screenshot=await self.snapshot(),
        )
        self.pending = payload
        return payload

    async def mock(self):
        # Deterministic local-browser driver; explicitly labelled mock, never an LLM claim.
        await self.navigate()
        if urlsplit(self.page.url).path == "/form":
            await self.prepare(self.config["parameters"].get("fields", {}))
            await sync_to_async(self.request_approval, thread_sensitive=True)(
                self.pending
            )
            raise ApprovalPending()
        if urlsplit(self.page.url).path == "/dynamic":
            await self.page.get_by_label("分类").select_option("software")
            await self.page.locator("[data-product]").first.wait_for()
        rows = await self.collect()
        if self.config["parameters"].get("multi_page"):
            await self.page.get_by_role("button", name="下一页").click()
            await self.page.locator('[data-page="2"]').wait_for()
            rows += await self.collect()
        limit = self.config["parameters"].get("limit", 5)
        output = {"items": rows[:limit], "source_urls": [self.page.url]}
        await self.log(
            "extract_dom",
            {"count": len(output["items"]), "engine": "mock-browser"},
            safe_url(self.page.url),
            screenshot=await self.snapshot(),
        )
        return self.verify(output)

    def verify(self, output):
        parsed = validate_output(
            output, self.config["output_schema"], self.config["allowed_domains"]
        )
        if self.observed:
            for row in parsed["items"]:
                if row not in self.observed:
                    raise ValueError("模型输出与独立 DOM 证据不一致")
        elif self.evidence:
            for row in parsed["items"]:
                for value in row.values():
                    if not any(
                        str(value) in e["text"]
                        or str(value) in e["links"]
                        or str(value) == e["url"]
                        for e in self.evidence
                    ):
                        raise ValueError("字段未在独立网页证据中找到")
        else:
            raise ValueError("尚无独立网页证据，不能判定采集成功")
        expected = self.config["parameters"].get("limit")
        if expected and len(parsed["items"]) != expected:
            raise ValueError("结果数量不满足任务验收条件")
        return parsed

    async def resume(self):
        await self.navigate()
        payload = self.approval["payload"]
        await self.prepare(payload["fields"])
        if fingerprint(self.pending) != self.approval["fingerprint"]:
            raise ValueError("审批后页面或参数已变更，禁止提交")
        # Consume before external side effect: ambiguous failures must never auto-replay.
        await sync_to_async(self.consume, thread_sensitive=True)(self.approval["id"])
        self.allow_post = True
        try:
            await self.page.locator('[name="idempotency_key"]').evaluate(
                "(el,value)=>el.value=value", self.approval["id"]
            )
            await self.page.get_by_role("button", name="提交申请").click()
            await self.page.locator("[data-receipt]").wait_for()
            receipt = await self.page.locator("[data-receipt]").get_attribute(
                "data-receipt"
            )
            if not receipt:
                raise ValueError("未收到服务端回执")
            await self.log(
                "approved_submit",
                {"approval_id": self.approval["id"], "receipt": receipt},
                safe_url(self.page.url),
                screenshot=await self.snapshot(),
            )
            return validate_output(
                {
                    "items": [{"receipt": receipt, **payload["fields"]}],
                    "source_urls": [self.page.url],
                },
                self.config["output_schema"],
                self.config["allowed_domains"],
            )
        finally:
            self.allow_post = False

    async def live(self, cdp_url):
        if not self.llm and (
            settings.MODEL_PROVIDER != "openai-compatible" or not settings.MODEL_API_KEY
        ):
            raise ValueError("请配置 OpenAI 兼容模型及服务端 API Key")
        from browser_use import Agent, BrowserSession, ChatOpenAI, Tools, ActionResult

        # Explicit allowlist: no arbitrary click, JS, upload, filesystem or keyboard action.
        from browser_use.tools.service import Tools as DefaultTools

        all_names = set(DefaultTools().registry.registry.actions)
        tools = Tools(
            exclude_actions=list(
                all_names
                - {
                    "navigate",
                    "extract",
                    "scroll",
                    "wait",
                    "done",
                    "search_page",
                    "find_elements",
                }
            )
        )
        service = self

        @tools.action(
            "Extract product rows from current page and save independently observed structured data"
        )
        async def save_structured_data(items: list[dict] | None = None) -> ActionResult:
            pages = [p for p in service.context.pages if p.url != "about:blank"]
            if pages:
                service.page = pages[-1]
            rows = await service.collect()
            service.saved = {
                "items": items or service.observed,
                "source_urls": list(dict.fromkeys(e["url"] for e in service.evidence)),
            }
            return ActionResult(extracted_content=json.dumps(service.saved))

        @tools.action(
            "Validate extracted product data using independent page evidence and configured output schema"
        )
        async def validate_extraction() -> ActionResult:
            return ActionResult(
                extracted_content=json.dumps(service.verify(service.saved or {}))
            )

        @tools.action("Get business task parameters")
        async def get_task_parameters() -> ActionResult:
            return ActionResult(
                extracted_content=json.dumps(service.config["parameters"])
            )

        @tools.action("Save current page screenshot artifact (at most three per run)")
        async def save_artifact() -> ActionResult:
            if service.artifact_count >= 3:
                return ActionResult(error="Artifact limit reached")
            service.artifact_count += 1
            path = await service.snapshot()
            await service.log(
                "save_artifact", {}, safe_url(service.page.url), screenshot=path
            )
            return ActionResult(extracted_content="Screenshot saved")

        @tools.action(
            "Fill the demo application form and request human approval before submit. Fields must include applicant, department, reason."
        )
        async def request_human_approval(fields: dict[str, str]) -> ActionResult:
            await service.prepare(fields)
            return ActionResult(
                is_done=True,
                extracted_content="Prepared operation; awaiting human approval",
            )

        @tools.action(
            "Interact with the isolated demo catalog: choose software filter or move to next page. No arbitrary selectors or writes."
        )
        async def demo_catalog_action(operation: str) -> ActionResult:
            if not settings.ALLOW_DEMO or not service.page.url.startswith(
                settings.DEMO_ORIGIN.rstrip("/") + "/"
            ):
                return ActionResult(error="Only available on isolated demo")
            if operation == "next_page":
                await service.page.get_by_role("button", name="下一页").click()
                await service.page.locator('[data-page="2"]').wait_for()
            elif operation == "filter_software":
                await service.page.get_by_label("分类").select_option("software")
                await service.page.locator("[data-product]").first.wait_for()
            else:
                return ActionResult(error="Unsupported operation")
            return ActionResult(extracted_content="Catalog updated")

        browser = BrowserSession(
            cdp_url=cdp_url,
            allowed_domains=self.config["allowed_domains"],
            keep_alive=True,
        )
        llm = self.llm or ChatOpenAI(
            model=self.config["model_name"],
            api_key=settings.MODEL_API_KEY,
            base_url=settings.MODEL_BASE_URL,
            max_retries=1,
        )
        agent = Agent(
            task=self.config["description"]
            + "\nStart URL: "
            + self.config["target_url"]
            + "\nUse save_structured_data and validate_extraction for results. Use request_human_approval for forms.",
            llm=llm,
            browser_session=browser,
            tools=tools,
            use_vision=False,
            generate_gif=False,
            max_actions_per_step=1,
            enable_planning=False,
        )

        async def on_end(a):
            # Attached CDP shares the persistent context; selected tab may change after navigation.
            pages = [p for p in self.context.pages if p.url != "about:blank"]
            if pages:
                self.page = pages[-1]
            item = a.history.history[-1] if a.history.history else None
            actions = (
                item.model_output.model_dump().get("action", [])
                if item and item.model_output
                else []
            )
            errors = [r.error for r in (item.result if item else []) if r.error]
            duration = (
                item.metadata.step_end_time - item.metadata.step_start_time
                if item and item.metadata
                else 0
            )
            await self.log(
                "agent_step",
                {"actions": actions},
                safe_url(self.page.url),
                duration=duration,
                error="; ".join(errors),
                screenshot=await self.snapshot(),
            )

        try:
            history = await agent.run(
                max_steps=self.config["max_steps"], on_step_end=on_end
            )
            self.raw_result = history.final_result() or ""
            self.usage = history.usage.model_dump(mode="json") if history.usage else {}
            if self.pending:
                await sync_to_async(self.request_approval, thread_sensitive=True)(
                    self.pending
                )
                raise ApprovalPending()
            if not history.is_successful():
                raise ValueError("Agent 未成功完成执行")
            if not self.saved:
                raise ValueError("Agent 未提交可验证的结构化数据")
            return self.verify(self.saved)
        finally:
            await browser.stop()
