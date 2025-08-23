# Generated manually to rename OnlyStudentNew to OnlyStudent
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0025_remove_old_onlystudent_table'),
    ]

    operations = [
        # Rename OnlyStudentNew to OnlyStudent
        migrations.RenameModel(
            old_name='OnlyStudentNew',
            new_name='OnlyStudent',
        ),
    ]
