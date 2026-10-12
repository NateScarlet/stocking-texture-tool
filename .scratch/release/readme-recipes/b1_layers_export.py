"""The B1 black picture (b1-black-original.png, rebuilt through the API with b1_setup.py) exported with 细线 and 加濑风 laid
over each other in four ratios, for the README's 纹理层 picture (demo-images.md, section 3). The four finished pictures go
to the asset library as b1-black-layers-<NNN>.png, NNN being 加濑风's share (000 is 细线 alone, 100 加濑风 alone); the README
crops the same patch of the left thigh out of each (make_readme_images.py).

Run with the isolated server up on port 8790 and B1 rebuilt in it:

    cd D:\\Video\\assets\\stocking-promo\\prompts
    python b1_setup.py D:\\Video\\assets\\stocking-promo\\readme\\b1-black-original.png
    python D:\\Stocking\\.scratch\\release\\readme-recipes\\b1_layers_export.py

The settings are b1_texture_zh.json's (细线, density 100, strength automatic, sparkles off), a second layer in 加濑风 (the
style a new layer starts with), Auto 100% on: the weights are the ratio, so 70 and 30 mix 70% and 30%. At 0 and 100 only one
layer is drawn, so those two are the styles alone: 000 must be the same picture as b1-black-finished.png. Needs a Python
with requests (the 3.12 install has it; the project's .venv does not).
"""
import sys

sys.path.insert(0, r'D:\Video\assets\stocking-promo\prompts')
import stk  # noqa: E402

LIB = r'D:\Video\assets\stocking-promo\readme'
SHARES = (0, 30, 70, 100)

st = stk.doc()
print([(r['name'], r['status'], r['strokes'], r['unguided']) for r in st['regions']], 'dividers', len(st['dividers']))
BASE = dict(style='knit', density=100, tilt=32, strength=100, strength_auto=True, sparkle_depth=0, sparkle_bright=0,
            sparkle_painted=0, sparkle_even=0, sparkle_link=True, moire_on=False, lock_total=True)
print('faded at density 100 (expect 0.0008):', {k: round(v, 4) for k, v in stk.look_get(**BASE)['check'].items()})
for share in SHARES:
    path = rf'{LIB}\b1-black-layers-{share:03d}.png'
    params = dict(BASE, weight=100 - share, layers=[dict(style='grain', weight=share)])
    res = stk.call('POST', f'/api/doc/{stk.did()}/export', {'kind': 'png', 'path': path, 'params': params})
    print(share, res['file'], res['notes'])
