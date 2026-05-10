from src.services.file_factory import FileFactory


def test_html_to_text_strips_tags():
    factory = FileFactory(output_dir="generated_images")
    text = factory._html_to_text("<h1>Titulo</h1><p>Hola <b>mundo</b></p>")
    assert "Titulo" in text
    assert "Hola mundo" in text
    assert "<h1>" not in text
