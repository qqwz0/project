# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0023_migrate_students_to_new_structure'),
    ]

    operations = [
        # Add profile_link to OnlyTeacher
        migrations.AddField(
            model_name='onlyteacher',
            name='profile_link',
            field=models.URLField(blank=True, null=True, verbose_name='Посилання на профіль', help_text='Посилання на особистий сайт, LinkedIn, ResearchGate тощо'),
        ),
        
        # Add short_name to Faculty
        migrations.AddField(
            model_name='faculty',
            name='short_name',
            field=models.CharField(max_length=50, unique=True, verbose_name='Коротка назва англійською', help_text='Наприклад: electronics, philosophy, mechanics', default='electronics'),
            preserve_default=False,
        ),
        
        # Update cascade deletes for better data preservation
        migrations.AlterField(
            model_name='request',
            name='student_id',
            field=models.ForeignKey(limit_choices_to={'role': 'Студент'}, null=True, on_delete=models.SET_NULL, related_name='users_student_requests', to='users.customuser', unique=False),
        ),
        migrations.AlterField(
            model_name='request',
            name='teacher_id',
            field=models.ForeignKey(null=True, on_delete=models.SET_NULL, to='catalog.onlyteacher'),
        ),
        migrations.AlterField(
            model_name='teachertheme',
            name='teacher_id',
            field=models.ForeignKey(null=True, on_delete=models.SET_NULL, related_name='themes', to='catalog.onlyteacher'),
        ),
        migrations.AlterField(
            model_name='requestfile',
            name='uploaded_by',
            field=models.ForeignKey(null=True, on_delete=models.SET_NULL, to='users.customuser'),
        ),
        migrations.AlterField(
            model_name='filecomment',
            name='author',
            field=models.ForeignKey(null=True, on_delete=models.SET_NULL, to='users.customuser'),
        ),
    ]
