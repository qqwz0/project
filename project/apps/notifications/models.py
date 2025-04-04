from django.db import models
from django.urls import reverse

class Message(models.Model):
    message_text = models.TextField()
    is_read = models.BooleanField(default=False)
    recipient = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    sender = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='sender_notifications')
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, blank=True, null=True)  
    
    class Meta:
        ordering = ['-created_at']
    
    def get_absolute_url(self):
        return reverse("mark_as_read", kwargs={"pk": self.pk})
    
        
    def __str__(self):
        return self.message + f" sended by ({self.sender.first_name} {self.sender.last_name})"
