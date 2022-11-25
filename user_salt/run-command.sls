{{salt['pillar.get']('command')}}:
  cmd.run:
    - runas: {{salt['pillar.get']('user')}}

