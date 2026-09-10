import re, zipfile
from pathlib import Path
out=Path('.output/payload/robot-skills');out.mkdir(parents=True)
for name,directory in {'grasp-object':'grasp_object','semantic-navigation':'semantic_navigation','place-object':'place_object'}.items():
 root=Path('semantic_robot_skills/skills')/directory
 version=re.search(r'(?m)^version:\s*([^#\s]+)',(root/'SKILL.md').read_text())[1].strip("'\"")
 with zipfile.ZipFile(out/f'{name}-{version}.zip','w',zipfile.ZIP_DEFLATED) as z:
  for p in sorted(root.rglob('*')):
   if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.orig'):z.write(p,p.relative_to(root))
