   
def get_grade(score):
    """
    Assigns a letter grade based on a numerical score (out of 100),
    aligned with the report card's displayed grading keys.
    """
    if score is None:
        return "N/A"
    try:
        score = float(score)
    except ValueError:
        return "Invalid"
        
    if 80 <= score <= 100:
        return "A"
    elif 71 <= score < 80:
        return "B+"
    elif 60 <= score < 71:
        return "B"
    elif 50 <= score < 60:
        return "C"
    elif 45 <= score < 50:
        return "D"
    elif 40 <= score < 45:
        return "E" # New range for E
    elif 0 <= score < 40:
        return "F"
    else:
        return "Invalid"

def get_subject_remark(score):
    """
    Provides a text remark for a subject score, aligned with the new grading scale.
    Adjusted slightly to match typical academic remarks for the new ranges.
    """
    if score is None:
        return "No score recorded."
    try:
        score = float(score)
    except ValueError:
        return "Score out of typical range."
        
    if 80 <= score <= 100:
        return "Excellent"
    elif 71 <= score < 80:
        return "Very Good"
    elif 60 <= score < 71:
        return "Good"
    elif 50 <= score < 60:
        return "Average"
    elif 40 <= score < 50:
        return "Fair" # Combines D and E ranges for a single remark
    elif 0 <= score < 40:
        return "Poor"
    else:
        return "Score out of typical range."
# get_overall_remark remains largely acceptable but is slightly adjusted 
# for consistency with the new overall grade boundaries (75, 65, 55, 45).
def get_overall_remark(average_score):
    """
    Provides an overall term remark based on the average score.
    """
    if average_score is None:
        return "No overall average available."
    try:
        average_score = float(average_score)
    except ValueError:
        return "Average score out of typical range."
        
    if 75 <= average_score <= 100:
        return "Outstanding academic achievement this term. Keep up the excellent work!"
    elif 65 <= average_score < 75:
        return "Very good overall performance. Continue to strive for excellence."
    elif 55 <= average_score < 65:
        return "Good academic progress. Focus on improving weaker areas."
    elif 45 <= average_score < 55:
        return "Fair overall performance. Requires more dedication and effort across subjects."
    elif 0 <= average_score < 45:
        return "Below average performance. Urgent need for improvement and support."
    else:
        return "Average score out of typical range."
    

# # Mid Term Grading 
# results/utils/midterm_utils.py

"""
Mid-Term Grading Utilities
These functions normalize scores based on the maximum score for the exam,
calculate grades, provide subject remarks, and overall term remarks.
All calculations are aligned with the central exam max score.
"""

def normalize_score(score, max_score):
    """
    Converts a raw score to a percentage based on the exam's max score.
    
    Args:
        score (float | int | None): The student's raw score.
        max_score (float | int): The maximum possible score for the exam.

    Returns:
        float | None: Score as a percentage (0-100), rounded to 2 decimals,
                      or None if invalid inputs.
    """
    if score is None:
        return None
    try:
        score = float(score)
        max_score = float(max_score)
        if max_score <= 0:
            return None
        return round((score / max_score) * 100, 2)
    except (ValueError, TypeError):
        return None


def mdterm_get_grade(score, max_score=100):
    """
    Assigns a letter grade based on the score relative to the exam's max score.

    Args:
        score (float | int | None): Raw score for the student.
        max_score (float | int): Maximum possible score for the exam.

    Returns:
        str: Letter grade ("A", "B+", "B", etc.) or "N/A"/"Invalid".
    """
    if score is None:
        return "N/A"

    percentage = normalize_score(score, max_score)
    if percentage is None:
        return "Invalid"

    if 80 <= percentage <= 100:
        return "A"
    elif 71 <= percentage < 80:
        return "B+"
    elif 60 <= percentage < 71:
        return "B"
    elif 50 <= percentage < 60:
        return "C"
    elif 45 <= percentage < 50:
        return "D"
    elif 40 <= percentage < 45:
        return "E"
    elif 0 <= percentage < 40:
        return "F"
    else:
        return "Invalid"


def mdterm_get_subject_remark(score, max_score=100):
    """
    Provides a textual remark for a subject score, normalized to the exam's max score.

    Args:
        score (float | int | None): Raw score for the student.
        max_score (float | int): Maximum possible score for the exam.

    Returns:
        str: Subject remark corresponding to the score percentage.
    """
    if score is None:
        return "No score recorded."

    percentage = normalize_score(score, max_score)
    if percentage is None:
        return "Score out of typical range."

    if 80 <= percentage <= 100:
        return "Excellent."
    elif 71 <= percentage < 80:
        return "Very Good."
    elif 60 <= percentage < 71:
        return "Good."
    elif 50 <= percentage < 60:
        return "Average."
    elif 40 <= percentage < 50:
        return "Needs more effort."
    elif 0 <= percentage < 40:
        return "Poor."
    else:
        return "Score out of typical range."


# # Mid Term
# def mdterm_get_overall_remark(average_score, max_score=100):
#     """
#     Provides an overall remark for a term based on the average score,
#     normalized to the exam's max score.

#     Args:
#         average_score (float | int | None): Average score across subjects.
#         max_score (float | int): Maximum possible score for the exam.

#     Returns:
#         str: Overall remark for the student.
#     """
#     if average_score is None:
#         return "No overall average available."

#     percentage = normalize_score(average_score, max_score)
#     if percentage is None:
#         return "Average score out of typical range."

#     if 75 <= percentage <= 100:
#         return "Outstanding academic achievement this term. Keep up the excellent work!"
#     elif 65 <= percentage < 75:
#         return "Very good overall performance. Continue to strive for excellence."
#     elif 55 <= percentage < 65:
#         return "Good academic progress. Focus on improving weaker areas."
#     elif 45 <= percentage < 55:
#         return "Fair overall performance. Requires more dedication and effort across subjects."
#     elif 0 <= percentage < 45:
#         return "Below average performance. Urgent need for improvement and support."
#     else:
#         return "Average score out of typical range."



# ============================================
# OVERALL REMARK UTILITY
# ============================================

def mdterm_get_overall_remark(
    average_score,
    max_score=100,
    remark_type='teacher'
):
    """
    Generates overall report remark.

    Args:
        average_score:
            Student overall average.

        max_score:
            Exam setting maximum score.

        remark_type:
            teacher | head_teacher

    Returns:
        str
    """

    if average_score is None:
        return "No overall average available."

    percentage = normalize_score(
        average_score,
        max_score
    )

    if percentage is None:
        return "Average score out of typical range."

    # ============================================
    # TEACHER REMARKS
    # ============================================

    teacher_remarks = {

        'excellent': (
            "Outstanding academic achievement "
            "this term. Keep up the excellent work!"
        ),

        'very_good': (
            "Very good overall performance. "
            "Continue to strive for excellence."
        ),

        'good': (
            "Good academic progress. "
            "Focus on improving weaker areas."
        ),

        'fair': (
            "Fair overall performance. "
            "Requires more dedication and effort "
            "across subjects."
        ),

        'poor': (
            "Below average performance. "
            "Urgent need for improvement and support."
        )
    }

    # ============================================
    # HEAD TEACHER REMARKS
    # ============================================

    head_teacher_remarks = {

        'excellent': (
            "Excellent result. "
            "A highly commendable academic outing."
        ),

        'very_good': (
            "Very impressive performance. "
            "Keep maintaining high standards."
        ),

        'good': (
            "Good performance overall. "
            "More consistency will produce better results."
        ),

        'fair': (
            "Average performance observed. "
            "Greater academic commitment is encouraged."
        ),

        'poor': (
            "Performance is below expectation. "
            "Immediate academic improvement is necessary."
        )
    }

    remarks = (
        teacher_remarks
        if remark_type == 'teacher'
        else head_teacher_remarks
    )

    # ============================================
    # SCORE MAPPING
    # ============================================

    if 75 <= percentage <= 100:
        return remarks['excellent']

    elif 65 <= percentage < 75:
        return remarks['very_good']

    elif 55 <= percentage < 65:
        return remarks['good']

    elif 45 <= percentage < 55:
        return remarks['fair']

    elif 0 <= percentage < 45:
        return remarks['poor']

    return "Average score out of typical range."