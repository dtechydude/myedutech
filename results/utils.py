   


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
        return "Excellent."
    elif 71 <= score < 80:
        return "Very Good."
    elif 60 <= score < 71:
        return "Good."
    elif 50 <= score < 60:
        return "Average."
    elif 40 <= score < 50:
        return "Needs more effort." # Combines D and E ranges for a single remark
    elif 0 <= score < 40:
        return "Poor."
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