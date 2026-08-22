from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hopital', '0024_remove_allergie_patient_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='adresse',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='customuser',
            name='langues',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='customuser',
            name='specialite',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
    ]