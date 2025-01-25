from django.contrib import admin
from .models import User, Only_teacher, Request

admin.site.register(User)
admin.site.register(Only_teacher)
admin.site.register(Request)

