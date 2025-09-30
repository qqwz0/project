# Generated manually to remove old OnlyStudent table
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0024_add_teacher_link_and_faculty_short_name'),
    ]

    operations = [
        # Remove the old OnlyStudent model
        migrations.DeleteModel(
            name='OnlyStudent',
        ),
    ]
