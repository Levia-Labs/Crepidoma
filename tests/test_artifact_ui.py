import json
import shutil
import subprocess
from pathlib import Path

import artifact
import artifact_examples
import artifact_spec
import pytest

KIT = Path(artifact.KIT)
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node not installed")

HARNESS = """
const fs = require("fs"), vm = require("vm");
global.UIDICT = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
function node(tag) {
  return { tag, attrs: {}, kids: [], setAttribute(k, v) { this.attrs[k] = v; },
    appendChild(k) { this.kids.push(k); return k; }, textContent: "" };
}
const data = { textContent: process.argv[3] }, app = node("div");
global.document = { createElement: node, createElementNS: (n, t) => node(t),
  createTextNode: (t) => ({ text: t }), body: node("body"), addEventListener() {},
  getElementById: (id) => (id === "app" ? app : data) };
vm.runInThisContext(fs.readFileSync(process.argv[2], "utf8"));
%s
"""


def node_run(body, data=None):
    script = HARNESS % body
    args = [NODE, "-e", script, KIT / "ui.json", KIT / "core.js", json.dumps(data or {})]
    out = subprocess.run(
        [str(a) for a in args], capture_output=True, text=True, encoding="utf-8", check=True
    )
    return json.loads(out.stdout)


def marks(text):
    body = """
    const p = node("p"); R.mark(p, process.argv[4]);
    const map = (k) =>
      k.tag ? { tag: k.tag, attrs: k.attrs, text: k.textContent } : { text: k.text };
    console.log(JSON.stringify(p.kids.map(map)));
    """
    script = HARNESS % body
    argv = [NODE, "-e", script, KIT / "ui.json", KIT / "core.js", "{}", text]
    out = subprocess.run(
        [str(a) for a in argv], capture_output=True, text=True, encoding="utf-8", check=True
    )
    return json.loads(out.stdout)


def word(key, data):
    body = f'R.boot(); console.log(JSON.stringify(R.t("{key}")));'
    return node_run(body, {"title": "T", "sections": [], **data})


@needs_node
def test_https_link_is_a_real_anchor():
    (kid,) = marks("[docs](https://example.com/a?b=1)")
    assert kid["tag"] == "a"
    assert kid["attrs"]["href"] == "https://example.com/a?b=1"
    assert kid["attrs"]["rel"] == "noopener"
    assert kid["attrs"]["target"] == "_blank"


@needs_node
def test_link_label_is_text_never_markup():
    (kid,) = marks("[<img src=x onerror=alert(1)>](https://example.com)")
    assert kid["tag"] == "a"
    assert kid["text"] == "<img src=x onerror=alert(1)>"


@needs_node
@pytest.mark.parametrize(
    "raw", ["[x](javascript:alert(1))", "[x](http://example.com)", "[x](data:text/html,a)"]
)
def test_other_schemes_stay_plain_text(raw):
    kids = marks(raw)
    assert all("tag" not in k for k in kids)
    assert "".join(k["text"] for k in kids) == raw


@needs_node
def test_bold_and_code_still_work_next_to_a_link():
    tags = [k.get("tag") for k in marks("**b** `c` [l](https://e.com)")]
    assert tags == ["strong", None, "code", None, "a"]


@needs_node
def test_polish_lang_translates_chrome():
    assert word("requires", {"lang": "pl"}) == "Wymaga"


@needs_node
def test_unknown_lang_falls_back_to_english():
    assert word("requires", {"lang": "xx"}) == "Requires"


@needs_node
def test_regional_lang_uses_its_base_language():
    assert word("unlocks", {"lang": "pl-PL"}) == "Odblokowuje"


@needs_node
def test_ui_object_overrides_one_key():
    assert word("requires", {"lang": "pl", "ui": {"requires": "Potrzebuje"}}) == "Potrzebuje"
    assert word("unlocks", {"lang": "pl", "ui": {"requires": "Potrzebuje"}}) == "Odblokowuje"


@needs_node
def test_template_words_fill_their_variables():
    body = 'R.boot(); console.log(JSON.stringify(R.t("more", { n: 3 })));'
    assert node_run(body, {"title": "T", "sections": [], "lang": "pl"}) == "+3 więcej"


def test_every_language_has_the_same_keys():
    words = artifact_spec.ui_dictionary()
    assert set(words["pl"]) == set(words["en"])


def test_ui_key_outside_the_dictionary_is_rejected():
    spec = artifact_examples.example("cards")
    spec["ui"] = {"colour": "x"}
    assert artifact_spec.validate(spec) == ["spec:ui.colour: unknown field 'colour'"]


def test_ui_override_must_be_text():
    spec = artifact_examples.example("cards")
    spec["ui"] = {"requires": 3}
    assert artifact_spec.validate(spec) == ["spec:ui.requires: expected non-empty text"]


def test_built_page_carries_the_dictionary_before_core(tmp_path):
    src = tmp_path / "p.json"
    src.write_text(json.dumps(artifact_examples.example("cards")), encoding="utf-8")
    assert artifact.main(["build", str(src)]) == 0
    page = (tmp_path / "p.html").read_text(encoding="utf-8")
    assert page.index("var UIDICT=") < page.index("var R = (function")
    assert "Wymaga" in page


def test_board_note_and_lede_may_be_empty():
    spec = artifact_examples.example("board")
    band = spec["sections"][0]["bands"][0]
    band["lede"] = ""
    band["groups"][0]["note"] = ""
    band["groups"][0]["items"][0]["note"] = ""
    assert artifact_spec.validate(spec) == []


def test_board_note_must_still_be_text():
    spec = artifact_examples.example("board")
    spec["sections"][0]["bands"][0]["lede"] = 4
    assert artifact_spec.validate(spec) == ["spec:sections[0].bands[0].lede: expected text"]


def test_pivot_record_table_has_field_headers():
    source = (KIT / "pivot.js").read_text(encoding="utf-8")
    assert "sec.dims.concat(sec.measures)" in source
    assert 'class: "grid recs"' in source


def test_sankey_labels_have_a_halo_in_the_surface_token():
    css = (KIT / "kit.css").read_text(encoding="utf-8")
    assert ".snode text{paint-order:stroke;stroke:var(--surface)" in css


def test_graph_script_stays_within_the_line_budget():
    assert len((KIT / "graph.js").read_text(encoding="utf-8").splitlines()) <= 300


TONE_NAMES = ["out", "new", "keep", "wait", "bad", "neutral", *[f"c{i}" for i in range(1, 9)]]


def test_every_tone_has_an_on_token_in_all_three_blocks():
    css = (KIT / "kit.css").read_text(encoding="utf-8")
    for name in TONE_NAMES:
        assert css.count(f"--on-{name}:") == 3, name
        assert f".t-{name}{{--on:var(--on-{name});" in css, name


def test_treemap_and_selected_block_labels_use_the_tone_ink():
    css = (KIT / "kit.css").read_text(encoding="utf-8")
    assert ".tmb text{fill:var(--on);" in css
    assert ".blk.is-sel text{fill:var(--on)}" in css


def test_board_dot_stays_on_the_first_line():
    css = (KIT / "kit.css").read_text(encoding="utf-8")
    assert ".item{display:flex;align-items:flex-start;" in css
    assert ".item > span:first-child{flex:1 1 0;min-width:0}" in css


def test_treemap_fills_the_box_width_with_a_capped_height():
    source = (KIT / "treemap.js").read_text(encoding="utf-8")
    assert 's.style.width = "100%";' in source
    assert 's.style.height = H + "px";' in source
    assert "maxWidth" not in source


def test_layers_wrap_blocks_and_keep_the_full_label_in_a_tooltip():
    source = (KIT / "layers.js").read_text(encoding="utf-8")
    assert "perRow" in source
    assert "if (text.cut) R.tip(g, b.label);" in source
