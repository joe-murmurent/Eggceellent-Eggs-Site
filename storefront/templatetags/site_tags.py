from django import template

register = template.Library()


@register.filter
def is_inline_image(content_type):
    return content_type in {
        "image/avif",
        "image/bmp",
        "image/gif",
        "image/jpeg",
        "image/png",
        "image/webp",
    }
