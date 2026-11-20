"""
Code Parser - AST-based parsing for multiple programming languages.

Supports: Python, JavaScript, Java, C++, TypeScript, Go, Rust, etc.
Uses language-specific ASTs where possible, falls back to regex-based extraction.
"""

import ast
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from loguru import logger

from app.parsers.base import BaseParser, ParseResult
from app.core.exceptions import ParsingException


class CodeParser(BaseParser):
    """Parser for source code files with language-aware processing."""
    
    # Language detection patterns
    LANGUAGE_PATTERNS = {
        'python': ['.py', '.pyw', '.pyx'],
        'javascript': ['.js', '.jsx', '.mjs'],
        'typescript': ['.ts', '.tsx'],
        'java': ['.java'],
        'cpp': ['.cpp', '.cc', '.cxx', '.hpp', '.h'],
        'c': ['.c', '.h'],
        'go': ['.go'],
        'rust': ['.rs'],
        'ruby': ['.rb'],
        'php': ['.php'],
        'swift': ['.swift'],
        'kotlin': ['.kt', '.kts'],
        'scala': ['.scala'],
        'r': ['.r', '.R'],
        'shell': ['.sh', '.bash', '.zsh'],
        'sql': ['.sql'],
        'yaml': ['.yaml', '.yml'],
        'json': ['.json'],
        'xml': ['.xml'],
        'html': ['.html', '.htm'],
        'css': ['.css', '.scss', '.sass', '.less'],
    }
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = set(
            ext for exts in self.LANGUAGE_PATTERNS.values() for ext in exts
        )
    
    def can_parse(self, file_path: Path) -> bool:
        """Check if file is a supported code file."""
        return file_path.suffix.lower() in self.supported_extensions
    
    def parse(self, file_path: Path) -> ParseResult:
        """Parse code file with language-specific analysis."""
        try:
            # Detect language
            language = self._detect_language(file_path)
            
            # Read file with encoding detection
            content = self._read_with_encoding(file_path)
            
            if not content.strip():
                raise ParsingException(
                    f"Empty code file: {file_path}",
                    parser_type="code",
                    file_path=str(file_path)
                )
            
            # Parse based on language
            metadata = {
                'language': language,
                'file_size': file_path.stat().st_size,
                'extension': file_path.suffix.lower(),
            }
            
            if language == 'python':
                text, extra_metadata = self._parse_python(content)
            elif language in ['javascript', 'typescript']:
                text, extra_metadata = self._parse_javascript(content)
            elif language == 'java':
                text, extra_metadata = self._parse_java(content)
            elif language in ['c', 'cpp']:
                text, extra_metadata = self._parse_c_cpp(content)
            else:
                # Generic parsing for other languages
                text, extra_metadata = self._parse_generic(content, language)
            
            metadata.update(extra_metadata)
            
            return ParseResult(
                text=text,
                metadata=metadata,
                success=True
            )
            
        except Exception as e:
            logger.error(f"Code parsing failed for {file_path}: {e}")
            raise ParsingException(
                f"Failed to parse code file: {str(e)}",
                parser_type="code",
                file_path=str(file_path),
                original_error=e
            )
    
    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension."""
        ext = file_path.suffix.lower()
        
        for language, extensions in self.LANGUAGE_PATTERNS.items():
            if ext in extensions:
                return language
        
        return 'unknown'
    
    def _read_with_encoding(self, file_path: Path) -> str:
        """Read file with multiple encoding attempts."""
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except (UnicodeDecodeError, LookupError):
                continue
        
        # Last resort: read as binary and decode with errors='replace'
        with open(file_path, 'rb') as f:
            return f.read().decode('utf-8', errors='replace')
    
    def _parse_python(self, content: str) -> tuple[str, Dict[str, Any]]:
        """Parse Python code using AST."""
        try:
            tree = ast.parse(content)
            
            # Extract structural information
            classes = []
            functions = []
            imports = []
            docstrings = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes.append({
                        'name': node.name,
                        'line': node.lineno,
                        'docstring': ast.get_docstring(node),
                        'methods': [m.name for m in node.body if isinstance(m, ast.FunctionDef)]
                    })
                elif isinstance(node, ast.FunctionDef):
                    # Only top-level functions
                    if node.col_offset == 0:
                        functions.append({
                            'name': node.name,
                            'line': node.lineno,
                            'docstring': ast.get_docstring(node),
                            'args': [arg.arg for arg in node.args.args]
                        })
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        imports.extend([alias.name for alias in node.names])
                    else:
                        module = node.module or ''
                        imports.append(module)
            
            # Extract module docstring
            module_docstring = ast.get_docstring(tree)
            if module_docstring:
                docstrings.append(module_docstring)
            
            # Build structured text representation
            text_parts = []
            
            if module_docstring:
                text_parts.append(f"Module Documentation:\n{module_docstring}\n")
            
            if imports:
                text_parts.append(f"Imports: {', '.join(set(imports))}\n")
            
            if classes:
                text_parts.append(f"\nClasses ({len(classes)}):")
                for cls in classes:
                    text_parts.append(f"  - {cls['name']} (line {cls['line']})")
                    if cls['docstring']:
                        text_parts.append(f"    {cls['docstring'][:100]}...")
            
            if functions:
                text_parts.append(f"\nFunctions ({len(functions)}):")
                for func in functions:
                    args_str = ', '.join(func['args'])
                    text_parts.append(f"  - {func['name']}({args_str}) (line {func['line']})")
                    if func['docstring']:
                        text_parts.append(f"    {func['docstring'][:100]}...")
            
            # Add full content for semantic search
            text_parts.append(f"\n\nFull Source Code:\n{content}")
            
            metadata = {
                'classes': [cls['name'] for cls in classes],
                'functions': [func['name'] for func in functions],
                'imports': list(set(imports)),
                'class_count': len(classes),
                'function_count': len(functions),
                'lines_of_code': len(content.splitlines()),
                'has_docstrings': len(docstrings) > 0,
            }
            
            return '\n'.join(text_parts), metadata
            
        except SyntaxError as e:
            logger.warning(f"Python syntax error, falling back to generic parsing: {e}")
            return self._parse_generic(content, 'python')
    
    def _parse_javascript(self, content: str) -> tuple[str, Dict[str, Any]]:
        """Parse JavaScript/TypeScript code using regex patterns."""
        # Extract functions
        function_pattern = r'(?:async\s+)?function\s+(\w+)\s*\([^)]*\)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>'
        functions = re.findall(function_pattern, content)
        function_names = [f[0] or f[1] for f in functions]
        
        # Extract classes
        class_pattern = r'class\s+(\w+)(?:\s+extends\s+\w+)?'
        classes = re.findall(class_pattern, content)
        
        # Extract imports
        import_pattern = r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]|require\([\'"]([^\'"]+)[\'"]\)'
        imports = re.findall(import_pattern, content)
        import_names = [imp[0] or imp[1] for imp in imports]
        
        # Extract exports
        export_pattern = r'export\s+(?:default\s+)?(?:class|function|const|let|var)\s+(\w+)'
        exports = re.findall(export_pattern, content)
        
        # Build text representation
        text_parts = [
            f"JavaScript/TypeScript Code Analysis",
            f"Functions: {', '.join(function_names[:10])}" if function_names else "No functions found",
            f"Classes: {', '.join(classes)}" if classes else "No classes found",
            f"Imports: {', '.join(import_names[:10])}" if import_names else "No imports",
            f"Exports: {', '.join(exports[:10])}" if exports else "No exports",
            f"\nFull Source Code:\n{content}"
        ]
        
        metadata = {
            'functions': function_names,
            'classes': classes,
            'imports': import_names,
            'exports': exports,
            'function_count': len(function_names),
            'class_count': len(classes),
            'lines_of_code': len(content.splitlines()),
        }
        
        return '\n'.join(text_parts), metadata
    
    def _parse_java(self, content: str) -> tuple[str, Dict[str, Any]]:
        """Parse Java code using regex patterns."""
        # Extract package
        package_pattern = r'package\s+([\w.]+);'
        package = re.search(package_pattern, content)
        package_name = package.group(1) if package else None
        
        # Extract imports
        import_pattern = r'import\s+(?:static\s+)?([\w.]+);'
        imports = re.findall(import_pattern, content)
        
        # Extract classes/interfaces
        class_pattern = r'(?:public\s+)?(?:abstract\s+)?(?:class|interface|enum)\s+(\w+)'
        classes = re.findall(class_pattern, content)
        
        # Extract methods
        method_pattern = r'(?:public|private|protected)\s+(?:static\s+)?(?:\w+)\s+(\w+)\s*\([^)]*\)'
        methods = re.findall(method_pattern, content)
        
        text_parts = [
            f"Java Code Analysis",
            f"Package: {package_name}" if package_name else "No package declaration",
            f"Classes/Interfaces: {', '.join(classes)}" if classes else "No classes found",
            f"Methods: {', '.join(methods[:10])}" if methods else "No methods found",
            f"Imports: {', '.join(imports[:10])}" if imports else "No imports",
            f"\nFull Source Code:\n{content}"
        ]
        
        metadata = {
            'package': package_name,
            'classes': classes,
            'methods': methods,
            'imports': imports,
            'class_count': len(classes),
            'method_count': len(methods),
            'lines_of_code': len(content.splitlines()),
        }
        
        return '\n'.join(text_parts), metadata
    
    def _parse_c_cpp(self, content: str) -> tuple[str, Dict[str, Any]]:
        """Parse C/C++ code using regex patterns."""
        # Extract includes
        include_pattern = r'#include\s*[<"]([^>"]+)[>"]'
        includes = re.findall(include_pattern, content)
        
        # Extract function declarations/definitions
        function_pattern = r'(?:(?:\w+)\s+)+(\w+)\s*\([^)]*\)\s*(?:{|;)'
        functions = re.findall(function_pattern, content)
        
        # Extract classes (C++)
        class_pattern = r'class\s+(\w+)'
        classes = re.findall(class_pattern, content)
        
        # Extract structs
        struct_pattern = r'struct\s+(\w+)'
        structs = re.findall(struct_pattern, content)
        
        # Extract defines
        define_pattern = r'#define\s+(\w+)'
        defines = re.findall(define_pattern, content)
        
        text_parts = [
            f"C/C++ Code Analysis",
            f"Includes: {', '.join(includes[:10])}" if includes else "No includes",
            f"Functions: {', '.join(functions[:10])}" if functions else "No functions",
            f"Classes: {', '.join(classes)}" if classes else "No classes",
            f"Structs: {', '.join(structs)}" if structs else "No structs",
            f"Defines: {', '.join(defines[:10])}" if defines else "No defines",
            f"\nFull Source Code:\n{content}"
        ]
        
        metadata = {
            'includes': includes,
            'functions': functions,
            'classes': classes,
            'structs': structs,
            'defines': defines,
            'function_count': len(functions),
            'lines_of_code': len(content.splitlines()),
        }
        
        return '\n'.join(text_parts), metadata
    
    def _parse_generic(self, content: str, language: str) -> tuple[str, Dict[str, Any]]:
        """Generic parsing for unsupported languages."""
        lines = content.splitlines()
        
        # Extract comments (common patterns)
        comment_patterns = [
            r'#.*$',  # Python, Ruby, Shell
            r'//.*$',  # C++, Java, JavaScript
            r'/\*.*?\*/',  # C, Java, JavaScript (block)
        ]
        
        comments = []
        for pattern in comment_patterns:
            comments.extend(re.findall(pattern, content, re.MULTILINE))
        
        # Basic statistics
        text_parts = [
            f"{language.title()} Code",
            f"Lines of Code: {len(lines)}",
            f"Comments Found: {len(comments)}",
            f"\nFull Source Code:\n{content}"
        ]
        
        metadata = {
            'lines_of_code': len(lines),
            'comment_count': len(comments),
            'non_empty_lines': len([line for line in lines if line.strip()]),
        }
        
        return '\n'.join(text_parts), metadata
    
    def get_supported_extensions(self) -> Set[str]:
        """Get set of supported file extensions."""
        return self.supported_extensions
