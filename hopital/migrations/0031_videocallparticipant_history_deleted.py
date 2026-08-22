from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('hopital', '0030_videocallparticipant_accepted'),
    ]

    operations = [
        migrations.AddField(
            model_name='videocallparticipant',
            name='history_deleted',
            field=models.BooleanField(default=False),
        ),
    ]