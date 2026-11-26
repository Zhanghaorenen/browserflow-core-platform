from django.core.management.base import BaseCommand
from django.conf import settings
from apps.core.models import TaskTemplate
from urllib.parse import urlsplit


class Command(BaseCommand):
    help = "Seed three usable, read-only demo templates; no fake production runs"

    def handle(self, *args, **kwargs):
        for name, path, prompt, params, approval in [
            (
                "公开信息采集",
                "/products",
                "访问目标网页，提取前五条产品的 name、price、url，并保存结构化数据。",
                {"limit": 5},
                False,
            ),
            (
                "多网页信息汇总",
                "/products",
                "访问产品目录，提取第一页和第二页的全部产品并汇总。",
                {"multi_page": True, "limit": 10},
                False,
            ),
            (
                "企业表单申请",
                "/form",
                "获取任务参数，填写企业申请表，使用 request_human_approval 请求审批后结束，禁止直接提交。",
                {
                    "fields": {
                        "applicant": "演示申请人",
                        "department": "研发部",
                        "reason": "申请测试环境资源",
                    }
                },
                True,
            ),
        ]:
            TaskTemplate.objects.update_or_create(
                owner=None,
                name=name,
                defaults={
                    "description": prompt,
                    "prompt_template": prompt,
                    "requires_approval": approval,
                    "default_config": {
                        "target_url": settings.DEMO_ORIGIN + path,
                        "allowed_domains": [urlsplit(settings.DEMO_ORIGIN).hostname],
                        "parameters": params,
                        "max_steps": 20,
                        "timeout_seconds": 120,
                    },
                    "output_schema": {
                        "type": "object",
                        "required": ["items", "source_urls"],
                        "properties": {
                            "items": {"type": "array", "minItems": 1},
                            "source_urls": {"type": "array", "minItems": 1},
                        },
                    },
                },
            )
        self.stdout.write(self.style.SUCCESS("3 templates ready"))
