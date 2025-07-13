# schools/utils.py

def get_grade(score):
    """
    Assigns a letter grade based on a numerical score (out of 100).
    """
    if score is None:
        return "N/A"
    score = float(score) # Ensure it's a float for comparisons
    if 75 <= score <= 100:
        return "A"
    elif 65 <= score < 75:
        return "B"
    elif 55 <= score < 65:
        return "C"
    elif 45 <= score < 55:
        return "D"
    elif 0 <= score < 45:
        return "F"
    else:
        return "Invalid" # For scores outside the expected range (e.g., negative or >100)

def get_subject_remark(score):
    """
    Provides a text remark for a subject score.
    """
    if score is None:
        return "No score recorded."
    score = float(score)
    if 80 <= score <= 100:
        return "Excellent performance, strong understanding."
    elif 70 <= score < 80:
        return "Very good effort, consistent performance."
    elif 60 <= score < 70:
        return "Good performance, but minor areas for improvement."
    elif 50 <= score < 60:
        return "Fair performance, needs more dedication."
    elif 40 <= score < 50:
        return "Needs significant improvement and focused attention."
    elif 0 <= score < 40:
        return "Poor performance, immediate intervention required."
    else:
        return "Score out of typical range."

def get_overall_remark(average_score):
    """
    Provides an overall term remark based on the average score.
    """
    if average_score is None:
        return "No overall average available."
    average_score = float(average_score)
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