from src.services.file_factory import FileFactory


def test_enforce_pdf_layout_guardrails_injects_before_head_close():
    factory = FileFactory(output_dir="generated_images")
    html = "<html><head><title>X</title></head><body><h2>Titulo</h2><p>Texto</p></body></html>"
    out = factory._enforce_pdf_layout_guardrails(html)
    assert "superagente-pdf-guardrails" in out
    assert out.lower().find("superagente-pdf-guardrails") < out.lower().find("</head>")


def test_enforce_pdf_layout_guardrails_does_not_duplicate():
    factory = FileFactory(output_dir="generated_images")
    html = "<html><head></head><body>ok</body></html>"
    out1 = factory._enforce_pdf_layout_guardrails(html)
    out2 = factory._enforce_pdf_layout_guardrails(out1)
    assert out2.count("superagente-pdf-guardrails") == 1


def test_group_headings_with_following_block_wraps_pair():
    factory = FileFactory(output_dir="generated_images")
    html = "<h2>Sección</h2><p>Contenido inicial</p><p>Otro párrafo</p>"
    out = factory._group_headings_with_following_block(html)
    assert 'class="sa-keep-with-next"' in out
    assert "<h2>Sección</h2><p>Contenido inicial</p>" in out


def test_apply_corporate_print_template_injects_header_footer():
    factory = FileFactory(output_dir="generated_images")
    html = "<html><body><h1>Título</h1><p>Texto</p></body></html>"
    out = factory._apply_corporate_print_template(html)
    assert "sa-corp-header" in out
    assert "sa-corp-footer" in out
    assert out.lower().count("sa-corp-header") == 1


def test_enforce_guardrails_tunes_paragraph_spacing():
    factory = FileFactory(output_dir="generated_images")
    html = "<html><head></head><body><h2>Sección</h2><p>A</p></body></html>"
    out = factory._enforce_pdf_layout_guardrails(html)
    assert "margin: 0 0 9px 0" in out
    assert "page-break-inside: auto" in out
