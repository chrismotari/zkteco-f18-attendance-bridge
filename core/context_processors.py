"""
Context processors to add global variables to all templates.
"""
from .models import OutlierPunch


def outlier_count(request):
    """
    Add unreviewed outlier count to all template contexts.
    """
    try:
        count = OutlierPunch.objects.filter(reviewed=False).count()
    except Exception:
        count = 0
    
    return {
        'unreviewed_outliers_count': count
    }
