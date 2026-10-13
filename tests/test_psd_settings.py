"""The 纹理 settings (look, 颜色排除) travel in a guides PSD's XMP: written by the guides export, read back on open."""
import io
import os

import numpy as np
import pytest
from psd_tools import PSDImage
from psd_tools.constants import Resource
from psd_tools.psd.image_resources import ImageResource

from stocking import export, look, psd_io
from stocking.document import Document

NS = psd_io.SETTINGS_NS


@pytest.fixture
def doc():
    d = Document(np.full((40, 60, 3), 120, np.uint8), 'synthetic.png')
    mask = np.zeros((40, 60), bool)
    mask[5:35, 10:50] = True
    with d.lock:
        d._new_region('左腿', mask)
        d._touch()
    yield d
    d.close()


def with_xmp(xmp, tmp_path):
    """A guides PSD whose XMP is `xmp` (str or bytes), as a path."""
    path = str(tmp_path / 'x.psd')
    psd_io.write_guides(path, np.full((40, 60, 3), 120, np.uint8), {}, np.zeros((40, 60), np.uint8))
    psd = PSDImage.open(path)
    data = xmp.encode('utf-8') if isinstance(xmp, str) else xmp
    key = Resource.XMP_METADATA.value
    psd.image_resources[key] = ImageResource(key=key, data=data)
    psd.save(path)
    return path


def packet(inner, attrs=''):
    return (f'<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?><x:xmpmeta xmlns:x="adobe:ns:meta/">'
            f'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
            f'<rdf:Description rdf:about="" xmlns:s="{NS}" xmlns:dc="http://purl.org/dc/elements/1.1/"{attrs}>{inner}'
            f'</rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end="w"?>')


JSON = '{"format":"stocking-texture-tool","version":1,"look":{"style":"grain","density":123},"color_exclude":false}'


def test_the_export_writes_the_settings_and_open_brings_them_back(doc, tmp_path):
    doc.look = look.clean_params({'style': 'grain', 'density': 120, 'moire_on': True, 'weight': 30,
                                  'layers': [{'style': 'lines', 'weight': 70, 'amount': 40.0}], 'lock_total': False})
    doc.color_exclude = False
    res = export.export(doc, None, None, str(tmp_path / 'g.psd'), 'guides')
    d2 = Document.open(res['file'])
    try:
        assert d2.look == doc.look and d2.color_exclude is False
        assert [r.name for r in d2.regions] == ['左腿']                 # the guides come back as before
        assert not d2.state()['can_undo_look']                          # what was read is where history starts
    finally:
        d2.close()


def test_a_file_has_no_settings_to_carry_while_they_are_all_default(doc, tmp_path):
    res = export.export(doc, None, None, str(tmp_path / 'g.psd'), 'guides')
    assert Resource.XMP_METADATA not in PSDImage.open(res['file']).image_resources.keys()
    assert psd_io.read_guide_layers(res['file'])['settings'] is None
    d2 = Document.open(res['file'])
    try:
        assert d2.look is None and d2.color_exclude is True
    finally:
        d2.close()


def test_colour_exclusion_alone_is_carried(doc, tmp_path):
    doc.color_exclude = False
    d2 = Document.open(export.export(doc, None, None, str(tmp_path / 'g.psd'), 'guides')['file'])
    try:
        assert d2.look is None and d2.color_exclude is False
    finally:
        d2.close()


def test_the_picture_is_the_same_with_or_without_settings(doc, tmp_path):
    plain = export.export(doc, None, None, str(tmp_path / 'a.psd'), 'guides')['file']
    doc.look = look.clean_params({'style': 'grain'})
    carrying = export.export(doc, None, None, str(tmp_path / 'b.psd'), 'guides')['file']
    a, b = psd_io.read_guide_layers(plain), psd_io.read_guide_layers(carrying)
    assert np.array_equal(a['art'], b['art']) and a['regions'].keys() == b['regions'].keys()
    assert [L.name for L in PSDImage.open(plain)] == [L.name for L in PSDImage.open(carrying)]


@pytest.mark.parametrize('how', ['element', 'attribute'])
def test_the_property_reads_as_an_element_or_as_an_attribute(how, tmp_path):
    """Photoshop writes simple properties as attributes of the description when it saves a file."""
    escaped = JSON.replace('&', '&amp;').replace('<', '&lt;').replace('"', '&quot;')
    xmp = packet(f'<s:settings>{JSON.replace("&", "&amp;")}</s:settings>') if how == 'element' \
        else packet('', f' s:settings="{escaped}"')
    got = psd_io.read_guide_layers(with_xmp(xmp, tmp_path))['settings']
    assert got['look'] == {'style': 'grain', 'density': 123} and got['color_exclude'] is False


def test_any_prefix_will_do_for_the_namespace(tmp_path):
    xmp = packet('').replace('xmlns:s=', 'xmlns:other=').replace('</rdf:Description>', f'<other:settings>{JSON}</other:settings></rdf:Description>')
    assert psd_io.read_guide_layers(with_xmp(xmp, tmp_path))['settings']['look']['style'] == 'grain'


@pytest.mark.parametrize('xmp', [
    b'',                                                                           # empty
    b'not xml at all',                                                             # damaged
    packet('<dc:title>Photoshop made this</dc:title>'),                           # XMP with nothing of ours
    packet('<s:settings>not json</s:settings>'),                                   # ours, but damaged
    packet('<s:settings>[1, 2]</s:settings>'),                                     # JSON of the wrong shape
    packet('<s:settings>{"format":"something-else","version":1}</s:settings>'),    # somebody else's mark
    packet('<s:settings>{"format":"stocking-texture-tool","version":2,"look":{"style":"grain"}}</s:settings>'),   # newer
    packet('<s:settings>{"format":"stocking-texture-tool","version":"1"}</s:settings>'),
    ('<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;&a;">]>' + packet('<s:settings>&b;</s:settings>')),
    pytest.param(b'<x' * 600000, id='too-big-to-bother-with'),
])
def test_settings_that_are_not_ours_or_not_usable_are_ignored_and_the_guides_still_open(xmp, tmp_path):
    path = with_xmp(xmp, tmp_path)
    assert psd_io.read_guide_layers(path)['settings'] is None
    d = Document.open(path)
    try:
        assert d.look is None and d.color_exclude is True
    finally:
        d.close()


def test_a_look_this_version_cannot_use_leaves_the_defaults_but_keeps_colour_exclusion(tmp_path):
    xmp = packet('<s:settings>{"format":"stocking-texture-tool","version":1,"look":{"style":"nope"},'
                 '"color_exclude":false}</s:settings>')
    d = Document.open(with_xmp(xmp, tmp_path))
    try:
        assert d.look is None and d.color_exclude is False
    finally:
        d.close()


def test_opening_from_bytes_brings_the_settings_back_too(doc, tmp_path):
    doc.look = look.clean_params({'style': 'oily'})
    path = export.export(doc, None, None, str(tmp_path / 'g.psd'), 'guides')['file']
    with open(path, 'rb') as f:
        d2 = Document.open(data=f.read(), filename='g.psd')
    try:
        assert d2.look['style'] == 'oily'
    finally:
        d2.close()
