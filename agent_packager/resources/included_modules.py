included_core_plugins = {% for plugin in core.plugins %} {{ plugin }}{% endfor %}
included_additional_plugins = {% for plugin in additional.plugins %} {{ plugin }}{% endfor %}
