import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_populate_group_template'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='group',
            name='unique_group_name_per_company',
        ),
        migrations.RemoveField(model_name='group', name='name'),
        migrations.RemoveField(model_name='group', name='can_access_inventory'),
        migrations.RemoveField(model_name='group', name='can_access_sales'),
        migrations.RemoveField(model_name='group', name='can_access_purchases'),
        migrations.RemoveField(model_name='group', name='can_access_users'),
        migrations.AlterField(
            model_name='group',
            name='template',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='groups', to='accounts.grouptemplate',
                verbose_name='Plantilla',
            ),
        ),
        migrations.AddConstraint(
            model_name='group',
            constraint=models.UniqueConstraint(fields=('company', 'template'), name='unique_template_per_company'),
        ),
    ]
