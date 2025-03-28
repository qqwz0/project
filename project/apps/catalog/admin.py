from django.contrib import admin
from .models import OnlyTeacher, OnlyStudent, Request

admin.site.register(OnlyTeacher)
admin.site.register(OnlyStudent)
admin.site.register(Request)

