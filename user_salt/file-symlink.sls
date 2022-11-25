# -*- coding: utf-8 -*-
# vim: set syntax=yaml ts=2 sw=2 sts=2 et :

{% if salt['file.directory_exists']({{salt['pillar.get']('symlink_path')}}) %}
{{salt['pillar.get']('symlink_path')}}:
  - file.rmdir
{% endif %}
{% if salt['file.file_exists']({{salt['pillar.get']('symlink_path')}}) %}
{{salt['pillar.get']('symlink_path')}}:
  - file.remove
{% endif %}

{{salt['pillar.get']('file_name')}}:
  file.symlink:
    - target: {{salt['pillar.get']('symlink_path')}}
