import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_grouptemplate'),
    ]

    operations = [
        migrations.AddField(
            model_name='group',
            name='template',
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='groups', to='accounts.grouptemplate',
                verbose_name='Plantilla',
            ),
        ),
    ]
