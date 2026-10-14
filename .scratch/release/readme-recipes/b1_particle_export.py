"""The B1 black picture (b1-black-original.png, rebuilt through the API with b1_setup.py) exported at 高光粒子 强度 0 / 35 / 70 / 100%
for the README's 高光粒子 picture (demo-images.md, section 3). The four finished pictures go to the asset library as
b1-black-particle-<NNN>.png; the README crops the same strip of the left thigh down to the knee out of each (make_readme_images.py).

Run with the isolated server up on port 8790 and B1 rebuilt in it:

    cd D:\\Video\\assets\\stocking-promo\\prompts
    python b1_setup.py D:\\Video\\assets\\stocking-promo\\readme\\b1-black-original.png
    python D:\\Stocking\\.scratch\\release\\readme-recipes\\b1_particle_export.py

The settings are b1_texture_zh.json's (细线, density 100, strength automatic, sparkles off); at 0 the switch is off (the
same picture as b1-black-layers-000.png), and at 35 / 70 / 100 the switch is on at that 强度. Needs a Python with requests
(the 3.12 install has it; the project's .venv does not).
"""
import sys

sys.path.insert(0, r'D:\Video\assets\stocking-promo\prompts')
import stk  # noqa: E402

LIB = r'D:\Video\assets\stocking-promo\readme'
STRENGTHS = (0, 35, 70, 100)

st = stk.doc()
print([(r['name'], r['status'], r['strokes'], r['unguided']) for r in st['regions']], 'dividers', len(st['dividers']))
BASE = dict(style='knit', density=100, tilt=32, strength=100, strength_auto=True, sparkle_depth=0, sparkle_bright=0,
            sparkle_painted=0, sparkle_even=0, sparkle_link=True, moire_on=False)
print('faded at density 100 (expect 0.0008):', {k: round(v, 4) for k, v in stk.look_get(**BASE)['check'].items()})
for s in STRENGTHS:
    path = rf'{LIB}\b1-black-particle-{s:03d}.png'
    params = dict(BASE, particle_on=s > 0, particle=s if s > 0 else 100)
    res = stk.call('POST', f'/api/doc/{stk.did()}/export', {'kind': 'png', 'path': path, 'params': params})
    print(s, res['file'], res['notes'])
