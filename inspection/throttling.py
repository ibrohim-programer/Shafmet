from rest_framework.throttling import SimpleRateThrottle

class CheckInRateThrottle(SimpleRateThrottle):
    """
    Check-in/out qilish so'rovlari sonini foydalanuvchi bo'yicha daqiqasiga 10 ta bilan cheklaydi.
    """
    rate = '10/min'

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = request.data.get('user_id') or self.get_ident(request)

        return self.cache_format % {
            'scope': 'check_in',
            'ident': ident
        }
