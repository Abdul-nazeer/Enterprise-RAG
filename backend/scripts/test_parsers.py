"""
Test all document parsers

Quick verification that parsers are importable and factory works
Note: Skips heavy dependencies (paddleocr, easyocr) for quick testing
"""

import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

def test_parser_initialization():
    """Test that all parsers can be initialized"""
    print("Testing Parser Initialization...")
    print("-" * 50)
    
    try:
        from app.parsers import ParserFactory
        
        # Get supported extensions
        extensions = ParserFactory.get_supported_extensions()
        print(f"✓ Supported extensions ({len(extensions)}):")
        for ext in sorted(extensions):
            print(f"  - {ext}")
        
        print("\n✓ ParserFactory initialized successfully!")
        
        # Test parser selection for different file types
        test_files = [
            "document.pdf",
            "image.png",
            "document.docx",
            "readme.md",
            "script.py",
            "diagram.mmd",
            "code.js",
            "style.css",
            "unknown.xyz"
        ]
        
        print("\nParser Selection Tests:")
        print("-" * 50)
        
        for filename in test_files:
            file_path = Path(filename)
            parser = ParserFactory.get_parser(file_path)
            if parser:
                print(f"✓ {filename:20} → {parser.__class__.__name__}")
            else:
                print(f"✗ {filename:20} → No parser found")
        
        return True
        
    except Exception as e:
        print(f"✗ Parser initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_parser_registry():
    """Test parser registry"""
    print("\n\nParser Registry:")
    print("-" * 50)
    
    # Test lightweight parsers only
    parsers_to_test = [
        ('PDFParser', 'app.parsers.pdf_parser'),
        ('DOCXParser', 'app.parsers.docx_parser'),
        ('TextParser', 'app.parsers.text_parser'),
        ('CodeParser', 'app.parsers.code_parser'),
        ('MermaidParser', 'app.parsers.mermaid_parser'),
    ]
    
    for parser_name, module_path in parsers_to_test:
        try:
            module = __import__(module_path, fromlist=[parser_name])
            parser_class = getattr(module, parser_name)
            parser = parser_class()
            print(f"✓ {parser_name:20} → Instantiated")
        except Exception as e:
            print(f"✗ {parser_name:20} → Failed: {e}")
            return False
    
    # Note about ImageParser
    print(f"⚠ ImageParser:20 → Skipped (requires paddleocr/easyocr)")
    
    return True


def main():
    """Run all parser tests"""
    print("="*50)
    print("PARSER VERIFICATION TESTS")
    print("="*50)
    print()
    
    # Test 1: Parser initialization
    init_success = test_parser_initialization()
    
    # Test 2: Parser registry
    registry_success = test_parser_registry()
    
    # Summary
    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    
    if init_success and registry_success:
        print("✓ All parser tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
