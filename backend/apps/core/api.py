from rest_framework.renderers import JSONRenderer
from rest_framework.views import exception_handler as drf_handler


class EnvelopeRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        status = renderer_context["response"].status_code
        return super().render(
            {
                "data": data if status < 400 else None,
                "error": data if status >= 400 else None,
            },
            accepted_media_type,
            renderer_context,
        )


def exception_handler(exc, context):
    from django.core.exceptions import ValidationError
    from rest_framework.exceptions import ValidationError as ApiError

    if isinstance(exc, (ValidationError, ValueError)):
        exc = ApiError(str(exc))
    return drf_handler(exc, context)
