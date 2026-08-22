from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('hopital', '0029_chatmessage_is_read'),
    ]

    operations = [
        migrations.AddField(
            model_name='videocallparticipant',
            name='accepted',
            field=models.BooleanField(default=False),
        ),
    ]