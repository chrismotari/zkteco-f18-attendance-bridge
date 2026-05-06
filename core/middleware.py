import pytz
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from attendance_bridge import settings


class TimezoneMiddleware(MiddlewareMixin):

    def process_request(self, request):
        # Skip for non-authenticated users or API requests
        if request.path.startswith('/api/') or request.path.startswith('/admin/'):
            return
        
        tz_name = None
        
        
        # 1. Check session for temporary override
        if not tz_name and hasattr(request, 'session'):
            tz_name = request.session.get('django_timezone')
        
        # 2. Check request header
        if not tz_name:
            tz_name = request.headers.get('Accept-Timezone')
        
        # 3. Check cookie set by JavaScript
        if not tz_name:
            tz_name = request.COOKIES.get('user_timezone')
        
        # 4. Use default from settings
        if not tz_name:
            tz_name = getattr(settings, 'DISPLAY_TIMEZONE', 'UTC')
        
        # Activate the timezone
        try:
            if tz_name and tz_name in pytz.all_timezones:
                timezone.activate(pytz.timezone(tz_name))
            else:
                timezone.activate(pytz.timezone('UTC'))
        except Exception:
            timezone.activate(pytz.timezone('UTC'))
        
        # Store in request for later use
        request.user_timezone = timezone.get_current_timezone_name()


class TimezoneContextMiddleware(MiddlewareMixin):
    """Add timezone info to template context."""
    
    def process_template_response(self, request, response):
        if hasattr(response, 'context_data') and response.context_data is not None:
            response.context_data['user_timezone'] = getattr(
                request, 'user_timezone',
                timezone.get_current_timezone_name()
            )
            response.context_data['available_timezones'] = pytz.common_timezones[:50]  # Limited for dropdown
        return response