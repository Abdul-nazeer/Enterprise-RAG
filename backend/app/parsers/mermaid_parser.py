"""
Mermaid Parser - Parse Mermaid diagram syntax.

Supports: flowchart, sequence, class, state, ER, gantt, pie, journey, etc.
Extracts diagram structure, nodes, relationships, and converts to text.
"""

import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger

from app.parsers.base import BaseParser, ParseResult
from app.core.exceptions import ParsingException


class MermaidParser(BaseParser):
    """Parser for Mermaid diagram files."""
    
    # Diagram type patterns
    DIAGRAM_TYPES = {
        'flowchart': r'(?:flowchart|graph)\s+(TD|TB|BT|RL|LR)',
        'sequence': r'sequenceDiagram',
        'class': r'classDiagram',
        'state': r'stateDiagram(?:-v2)?',
        'er': r'erDiagram',
        'gantt': r'gantt',
        'pie': r'pie',
        'journey': r'journey',
        'gitgraph': r'gitGraph',
        'requirement': r'requirementDiagram',
        'mindmap': r'mindmap',
        'timeline': r'timeline',
    }
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = {'.mmd', '.mermaid'}
    
    def can_parse(self, file_path: Path) -> bool:
        """Check if file is a Mermaid diagram."""
        # Only parse dedicated Mermaid files (.mmd, .mermaid)
        # Let TextParser handle .md files with embedded diagrams
        return file_path.suffix.lower() in self.supported_extensions
    
    def parse(self, file_path: Path) -> ParseResult:
        """Parse Mermaid diagram file."""
        try:
            content = self._read_file(file_path)
            
            if not content.strip():
                raise ParsingException(
                    f"Empty Mermaid file: {file_path}",
                    parser_type="mermaid",
                    file_path=str(file_path)
                )
            
            # Extract Mermaid code blocks if in markdown
            mermaid_blocks = self._extract_mermaid_blocks(content)
            
            if not mermaid_blocks:
                # Treat entire file as Mermaid syntax
                mermaid_blocks = [content]
            
            # Parse all blocks
            all_diagrams = []
            all_metadata = {
                'diagram_count': len(mermaid_blocks),
                'diagrams': []
            }
            
            for idx, block in enumerate(mermaid_blocks, 1):
                text, metadata = self._parse_mermaid_block(block, idx)
                all_diagrams.append(text)
                all_metadata['diagrams'].append(metadata)
            
            # Combine all diagram texts
            final_text = '\n\n---\n\n'.join(all_diagrams)
            
            return ParseResult(
                text=final_text,
                metadata=all_metadata,
                success=True
            )
            
        except Exception as e:
            logger.error(f"Mermaid parsing failed for {file_path}: {e}")
            raise ParsingException(
                f"Failed to parse Mermaid file: {str(e)}",
                parser_type="mermaid",
                file_path=str(file_path),
                original_error=e
            )
    
    def _read_file(self, file_path: Path) -> str:
        """Read file with encoding fallback."""
        encodings = ['utf-8', 'utf-8-sig', 'latin-1']
        
        for encoding in encodings:
            try:
                return file_path.read_text(encoding=encoding)
            except (UnicodeDecodeError, LookupError):
                continue
        
        # Last resort
        return file_path.read_text(encoding='utf-8', errors='replace')
    
    def _extract_mermaid_blocks(self, content: str) -> List[str]:
        """Extract Mermaid code blocks from markdown."""
        pattern = r'```mermaid\s*\n(.*?)```'
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
        return [match.strip() for match in matches]
    
    def _parse_mermaid_block(self, content: str, block_num: int) -> Tuple[str, Dict[str, Any]]:
        """Parse a single Mermaid diagram block."""
        # Detect diagram type
        diagram_type = self._detect_diagram_type(content)
        
        # Parse based on type
        if diagram_type == 'flowchart':
            return self._parse_flowchart(content, block_num)
        elif diagram_type == 'sequence':
            return self._parse_sequence(content, block_num)
        elif diagram_type == 'class':
            return self._parse_class(content, block_num)
        elif diagram_type == 'state':
            return self._parse_state(content, block_num)
        elif diagram_type == 'er':
            return self._parse_er(content, block_num)
        elif diagram_type == 'gantt':
            return self._parse_gantt(content, block_num)
        else:
            return self._parse_generic(content, diagram_type, block_num)
    
    def _detect_diagram_type(self, content: str) -> str:
        """Detect the type of Mermaid diagram."""
        first_line = content.strip().split('\n')[0].strip()
        
        for diagram_type, pattern in self.DIAGRAM_TYPES.items():
            if re.search(pattern, first_line, re.IGNORECASE):
                return diagram_type
        
        return 'unknown'
    
    def _parse_flowchart(self, content: str, block_num: int) -> Tuple[str, Dict[str, Any]]:
        """Parse flowchart/graph diagram."""
        # Extract direction
        direction_match = re.search(r'(?:flowchart|graph)\s+(TD|TB|BT|RL|LR)', content)
        direction = direction_match.group(1) if direction_match else 'TB'
        
        # Extract nodes (id[text] or id(text) or id{text})
        node_pattern = r'(\w+)[\[\(\{]([^\]\)\}]+)[\]\)\}]'
        nodes = re.findall(node_pattern, content)
        node_dict = {node_id: text for node_id, text in nodes}
        
        # Extract edges (connections)
        edge_patterns = [
            r'(\w+)\s*(?:-->|---)\s*(\w+)',  # Simple arrows
            r'(\w+)\s*(?:-->|---)\|([^|]+)\|\s*(\w+)',  # Labeled arrows
            r'(\w+)\s*(?:==>|===)\s*(\w+)',  # Bold arrows
            r'(\w+)\s*(?:-\.-|\.-\.)\s*(\w+)',  # Dotted lines
        ]
        
        edges = []
        for pattern in edge_patterns:
            matches = re.findall(pattern, content)
            if matches:
                edges.extend(matches)
        
        # Build text representation
        text_parts = [
            f"Flowchart Diagram (Block {block_num})",
            f"Direction: {direction}",
            f"\nNodes ({len(nodes)}):"
        ]
        
        for node_id, text in nodes:
            text_parts.append(f"  - {node_id}: {text}")
        
        text_parts.append(f"\nConnections ({len(edges)}):")
        for edge in edges[:20]:  # Limit to first 20
            if len(edge) == 2:
                text_parts.append(f"  - {edge[0]} → {edge[1]}")
            elif len(edge) == 3:
                text_parts.append(f"  - {edge[0]} --{edge[1]}--> {edge[2]}")
        
        # Add original syntax
        text_parts.append(f"\nOriginal Syntax:\n{content}")
        
        metadata = {
            'type': 'flowchart',
            'direction': direction,
            'node_count': len(nodes),
            'edge_count': len(edges),
            'nodes': list(node_dict.keys()),
        }
        
        return '\n'.join(text_parts), metadata
    
    def _parse_sequence(self, content: str, block_num: int) -> Tuple[str, Dict[str, Any]]:
        """Parse sequence diagram."""
        # Extract participants
        participant_pattern = r'participant\s+(\w+)(?:\s+as\s+(.+))?'
        participants = re.findall(participant_pattern, content)
        
        # Extract messages
        message_pattern = r'(\w+)\s*(->>|-->>|->>?\+|-->>?\+|->|-->)\s*(\w+)\s*:\s*(.+)'
        messages = re.findall(message_pattern, content)
        
        # Extract activations
        activation_pattern = r'(?:activate|deactivate)\s+(\w+)'
        activations = re.findall(activation_pattern, content)
        
        # Extract notes
        note_pattern = r'[Nn]ote\s+(?:right|left|over)\s+(?:of\s+)?(\w+)(?:\s*,\s*(\w+))?\s*:\s*(.+)'
        notes = re.findall(note_pattern, content)
        
        text_parts = [
            f"Sequence Diagram (Block {block_num})",
            f"\nParticipants ({len(participants)}):"
        ]
        
        for pid, alias in participants:
            display = alias if alias else pid
            text_parts.append(f"  - {pid}: {display}")
        
        text_parts.append(f"\nMessage Flow ({len(messages)}):")
        for idx, (sender, arrow, receiver, msg) in enumerate(messages[:30], 1):
            text_parts.append(f"  {idx}. {sender} → {receiver}: {msg}")
        
        if notes:
            text_parts.append(f"\nNotes ({len(notes)}):")
            for note_data in notes[:10]:
                text_parts.append(f"  - {note_data[-1]}")
        
        text_parts.append(f"\nOriginal Syntax:\n{content}")
        
        metadata = {
            'type': 'sequence',
            'participant_count': len(participants),
            'message_count': len(messages),
            'participants': [p[0] for p in participants],
        }
        
        return '\n'.join(text_parts), metadata
    
    def _parse_class(self, content: str, block_num: int) -> Tuple[str, Dict[str, Any]]:
        """Parse class diagram."""
        # Extract class definitions
        class_pattern = r'class\s+(\w+)\s*\{([^}]+)\}'
        classes = re.findall(class_pattern, content)
        
        # Extract relationships
        relationship_pattern = r'(\w+)\s*(<\||>|<\.\.|\.\.>|--|\.\.|o--o|<--o|--o|-->|\*--|\*\.\.)\s*(\w+)(?:\s*:\s*(.+))?'
        relationships = re.findall(relationship_pattern, content)
        
        text_parts = [
            f"Class Diagram (Block {block_num})",
            f"\nClasses ({len(classes)}):"
        ]
        
        for class_name, body in classes:
            members = [line.strip() for line in body.strip().split('\n') if line.strip()]
            text_parts.append(f"  - {class_name}")
            for member in members[:5]:  # First 5 members
                text_parts.append(f"    {member}")
        
        text_parts.append(f"\nRelationships ({len(relationships)}):")
        for src, rel, dst, label in relationships[:20]:
            label_str = f" ({label})" if label else ""
            text_parts.append(f"  - {src} {rel} {dst}{label_str}")
        
        text_parts.append(f"\nOriginal Syntax:\n{content}")
        
        metadata = {
            'type': 'class',
            'class_count': len(classes),
            'relationship_count': len(relationships),
            'classes': [cls[0] for cls in classes],
        }
        
        return '\n'.join(text_parts), metadata
    
    def _parse_state(self, content: str, block_num: int) -> Tuple[str, Dict[str, Any]]:
        """Parse state diagram."""
        # Extract states
        state_pattern = r'(?:state\s+"([^"]+)"\s+as\s+(\w+)|(\w+)\s*:\s*(.+))'
        states = re.findall(state_pattern, content)
        
        # Extract transitions
        transition_pattern = r'(\w+)\s*-->\s*(\w+)(?:\s*:\s*(.+))?'
        transitions = re.findall(transition_pattern, content)
        
        text_parts = [
            f"State Diagram (Block {block_num})",
            f"\nStates ({len(states)}):"
        ]
        
        for state_data in states:
            if state_data[0]:  # Named state
                text_parts.append(f"  - {state_data[1]}: {state_data[0]}")
            elif state_data[2]:  # Description state
                text_parts.append(f"  - {state_data[2]}: {state_data[3]}")
        
        text_parts.append(f"\nTransitions ({len(transitions)}):")
        for src, dst, condition in transitions[:20]:
            cond_str = f" [{condition}]" if condition else ""
            text_parts.append(f"  - {src} → {dst}{cond_str}")
        
        text_parts.append(f"\nOriginal Syntax:\n{content}")
        
        metadata = {
            'type': 'state',
            'state_count': len(states),
            'transition_count': len(transitions),
        }
        
        return '\n'.join(text_parts), metadata
    
    def _parse_er(self, content: str, block_num: int) -> Tuple[str, Dict[str, Any]]:
        """Parse entity-relationship diagram."""
        # Extract entities
        entity_pattern = r'(\w+)\s*\{([^}]+)\}'
        entities = re.findall(entity_pattern, content)
        
        # Extract relationships
        relationship_pattern = r'(\w+)\s*(\|\|--\|\||o\|--o\||\|\|--o\||o\|--\|\||\|\|--o\{|o\{--\|\||o\{--o\{)\s*(\w+)\s*:\s*(.+)'
        relationships = re.findall(relationship_pattern, content)
        
        text_parts = [
            f"Entity-Relationship Diagram (Block {block_num})",
            f"\nEntities ({len(entities)}):"
        ]
        
        for entity_name, attributes in entities:
            attrs = [line.strip() for line in attributes.strip().split('\n') if line.strip()]
            text_parts.append(f"  - {entity_name}")
            for attr in attrs[:5]:
                text_parts.append(f"    {attr}")
        
        text_parts.append(f"\nRelationships ({len(relationships)}):")
        for e1, rel, e2, label in relationships[:20]:
            text_parts.append(f"  - {e1} {rel} {e2}: {label}")
        
        text_parts.append(f"\nOriginal Syntax:\n{content}")
        
        metadata = {
            'type': 'er',
            'entity_count': len(entities),
            'relationship_count': len(relationships),
            'entities': [ent[0] for ent in entities],
        }
        
        return '\n'.join(text_parts), metadata
    
    def _parse_gantt(self, content: str, block_num: int) -> Tuple[str, Dict[str, Any]]:
        """Parse Gantt chart."""
        # Extract title
        title_match = re.search(r'title\s+(.+)', content)
        title = title_match.group(1) if title_match else "Untitled"
        
        # Extract sections
        section_pattern = r'section\s+(.+)'
        sections = re.findall(section_pattern, content)
        
        # Extract tasks
        task_pattern = r'(?:(?!section|title)\s*)(\w[^:]+)\s*:\s*(\w+)?,?\s*(\d{4}-\d{2}-\d{2})?,?\s*(\d+d)?'
        tasks = re.findall(task_pattern, content)
        
        text_parts = [
            f"Gantt Chart (Block {block_num})",
            f"Title: {title}",
            f"\nSections ({len(sections)}):"
        ]
        
        for section in sections:
            text_parts.append(f"  - {section}")
        
        text_parts.append(f"\nTasks ({len(tasks)}):")
        for task_name, status, date, duration in tasks[:30]:
            task_info = [task_name.strip()]
            if status:
                task_info.append(f"Status: {status}")
            if date:
                task_info.append(f"Start: {date}")
            if duration:
                task_info.append(f"Duration: {duration}")
            text_parts.append(f"  - {' | '.join(task_info)}")
        
        text_parts.append(f"\nOriginal Syntax:\n{content}")
        
        metadata = {
            'type': 'gantt',
            'title': title,
            'section_count': len(sections),
            'task_count': len(tasks),
        }
        
        return '\n'.join(text_parts), metadata
    
    def _parse_generic(self, content: str, diagram_type: str, block_num: int) -> Tuple[str, Dict[str, Any]]:
        """Generic parsing for unsupported diagram types."""
        lines = content.strip().split('\n')
        
        text_parts = [
            f"Mermaid Diagram (Block {block_num})",
            f"Type: {diagram_type}",
            f"Lines: {len(lines)}",
            f"\nOriginal Syntax:\n{content}"
        ]
        
        metadata = {
            'type': diagram_type,
            'line_count': len(lines),
        }
        
        return '\n'.join(text_parts), metadata
