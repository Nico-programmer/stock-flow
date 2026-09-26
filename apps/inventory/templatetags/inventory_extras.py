from django import template

register = template.Library()


# Django templates no pueden indexar un dict con una variable ({{ dict.key }} solo
# funciona con una clave literal): esto habilita {{ dict|get_item:variable }}.
@register.filter
def get_item(dictionary, key):
    if not dictionary:
        return None
    return dictionary.get(key)
