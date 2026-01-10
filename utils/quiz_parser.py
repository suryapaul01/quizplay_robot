"""
Bulk Quiz Format Parser

Parses questions in the format:
Question text here?
Option A ✅
Option B
Option C
Option D

Next question?
True ✅
False
"""
import re
from typing import List, Dict, Optional, Tuple


def parse_bulk_questions(text: str) -> Tuple[List[Dict], List[str]]:
    """
    Parse bulk question format and return list of questions
    
    Returns:
        Tuple of (parsed_questions, errors)
    """
    questions = []
    errors = []
    
    # Split by double newlines to separate questions
    blocks = re.split(r'\n\s*\n', text.strip())
    
    for i, block in enumerate(blocks, 1):
        if not block.strip():
            continue
            
        result = parse_single_question(block.strip())
        
        if result["success"]:
            questions.append(result["question"])
        else:
            errors.append(f"Question {i}: {result['error']}")
    
    return questions, errors


def parse_single_question(block: str) -> Dict:
    """
    Parse a single question block
    
    Format:
    Question text?
    Option 1 ✅
    Option 2
    Option 3
    ...
    """
    lines = [line.strip() for line in block.strip().split('\n') if line.strip()]
    
    if len(lines) < 3:
        return {
            "success": False,
            "error": "Need at least question + 2 options"
        }
    
    question_text = lines[0]
    options = []
    correct_index = -1
    
    for i, line in enumerate(lines[1:]):
        # Check for correct answer marker
        is_correct = '✅' in line or '✓' in line
        
        # Remove markers and clean option text
        option_text = line.replace('✅', '').replace('✓', '').strip()
        
        if not option_text:
            continue
            
        options.append(option_text)
        
        if is_correct:
            correct_index = len(options) - 1
    
    # Validate
    if len(options) < 2:
        return {
            "success": False,
            "error": "Need at least 2 options"
        }
    
    if len(options) > 10:
        return {
            "success": False,
            "error": "Maximum 10 options allowed"
        }
    
    if correct_index == -1:
        return {
            "success": False,
            "error": "No correct answer marked with ✅"
        }
    
    # Determine question type
    is_true_false = (
        len(options) == 2 and
        options[0].lower() in ['true', 'false'] and
        options[1].lower() in ['true', 'false']
    )
    
    question_type = "truefalse" if is_true_false else "mcq"
    
    return {
        "success": True,
        "question": {
            "question_text": question_text,
            "options": options,
            "correct_index": correct_index,
            "question_type": question_type
        }
    }


def validate_question_format(text: str) -> Tuple[bool, str]:
    """
    Validate if text follows the bulk question format
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not text.strip():
        return False, "Empty input"
    
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    
    if len(lines) < 3:
        return False, "Need at least question text + 2 options"
    
    has_correct_marker = any('✅' in line or '✓' in line for line in lines[1:])
    
    if not has_correct_marker:
        return False, "Mark correct answer with ✅"
    
    return True, ""


def format_question_preview(question: Dict) -> str:
    """Format a parsed question for preview"""
    text = f"❓ {question['question_text']}\n\n"
    
    for i, option in enumerate(question['options']):
        if i == question['correct_index']:
            text += f"✅ {option}\n"
        else:
            text += f"⚪ {option}\n"
    
    text += f"\n📝 Type: {question['question_type'].upper()}"
    return text
