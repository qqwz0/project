from django.http import HttpResponse
from django.contrib.auth.mixins import LoginRequiredMixin, AccessMixin
from django.shortcuts import redirect
from .models import Request


class HtmxModalFormAccessMixin(LoginRequiredMixin, AccessMixin):
    """
    A mixin that checks if the user is authenticated and is a student.
    Returns a 403 response for HTMX requests or redirects otherwise.
    """
    permission_required = 'users.role == "Студент"'
    raise_exception = True

    def handle_no_permission(self):
        """
        Handles scenarios where the user does not have permission.
        Returns a 403 for HTMX requests or redirects to 'teachers_catalog'.
        """
        if self.raise_exception or self.request.htmx:
            return HttpResponse(status=403)
        else:
            return redirect('catalog:teachers_catalog')

    def dispatch(self, request, *args, **kwargs):
        """
        Overridden dispatch method.
        Checks if the user is authenticated and not a teacher. Otherwise, calls `handle_no_permission`.
        """
        if 'pk' in self.kwargs:
             already_requested = Request.objects.filter(student_id=request.user, teacher_id=self.kwargs['pk'], request_status='Очікує').exists()
             if already_requested:
               return self.handle_no_permission()
           
        if Request.objects.filter(student_id=request.user, request_status='Активний').exists():  
            return self.handle_no_permission()  
            
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        if request.user.role == 'Викладач':
            return self.handle_no_permission()
        
        # If checks pass, proceed with the normal dispatch flow
        return super().dispatch(request, *args, **kwargs)


class FileAccessMixin(LoginRequiredMixin, AccessMixin):
    """
    A mixin that only checks if the user is authenticated.
    Returns a 403 response for HTMX requests or redirects otherwise.
    """
    raise_exception = True

    def handle_no_permission(self):
        """
        Handles scenarios where the user does not have permission.
        Returns a 403 for HTMX requests or redirects to login.
        """
        if self.raise_exception or self.request.htmx:
            return HttpResponse(status=403)
        else:
            return redirect('login')

    def dispatch(self, request, *args, **kwargs):
        """
        Overridden dispatch method.
        Only checks if the user is authenticated.
        """
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        return super().dispatch(request, *args, **kwargs)
