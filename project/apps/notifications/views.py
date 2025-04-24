from django.views.generic import ListView, View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Message



class MessageListView(LoginRequiredMixin,ListView):
    model = Message
    template_name = 'header.html'
    context_object_name = 'message_list'    
    def get_queryset(self):
        return Message.objects.filter(recipient=self.request.user).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['message_list'] = self.get_queryset()
        unread_messages = context['message_list'].filter(is_read=False)
        context['unread_count'] = unread_messages.count()
        context['unread'] = context['unread_count'] > 0
        return context
        


@method_decorator(csrf_exempt, name='dispatch') 
class MarkAsReadView(View):
    def post(self, request, message_id):
        message = get_object_or_404(Message, id=message_id, recipient=request.user)
        if not message.is_read:
            message.is_read = True
            message.save(update_fields=['is_read'])
        return JsonResponse({"status": "success", "is_read": message.is_read})
        
        
         