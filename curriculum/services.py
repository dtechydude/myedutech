import datetime


def get_non_schooling_dates(term):
    """
    Every date within the term that is NOT a valid school day:
    all Saturdays/Sundays, plus any PublicHoliday entered for the term.
    """
    dates = set()
    current = term.start_date
    while current <= term.end_date:
        if current.weekday() >= 5:  # 5=Saturday, 6=Sunday
            dates.add(current)
        current += datetime.timedelta(days=1)

    dates.update(term.public_holidays.values_list('date', flat=True))
    return dates


def get_term_calendar_school_days(term):
    """
    Total valid school days in a term: full calendar span minus weekends
    and public holidays. Used whenever no manual AttendanceConfiguration
    total has been entered for the term.
    """
    total_calendar_days = (term.end_date - term.start_date).days + 1
    return max(total_calendar_days - len(get_non_schooling_dates(term)), 0)


def is_non_schooling_day(term, check_date):
    """True if check_date is a weekend or a configured public holiday for this term."""
    if check_date.weekday() >= 5:
        return True
    return term.public_holidays.filter(date=check_date).exists()