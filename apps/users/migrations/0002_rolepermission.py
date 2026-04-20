from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0001_initial'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RolePermission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('owner', 'Owner'), ('admin', 'Admin'), ('manager', 'Manager'), ('viewer', 'Viewer')], max_length=20)),
                ('entity', models.CharField(choices=[('deals', 'Deals'), ('contacts', 'Contacts'), ('companies', 'Companies')], max_length=20)),
                ('can_view', models.BooleanField(default=False)),
                ('can_create', models.BooleanField(default=False)),
                ('can_update', models.BooleanField(default=False)),
                ('can_delete', models.BooleanField(default=False)),
                ('scope', models.CharField(choices=[('all', 'All records'), ('team', 'Team records'), ('own', 'Own records')], default='all', max_length=10)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='role_permissions', to='tenants.tenant')),
            ],
            options={
                'unique_together': {('tenant', 'role', 'entity')},
            },
        ),
        migrations.AddIndex(
            model_name='rolepermission',
            index=models.Index(fields=['tenant', 'role'], name='users_rolep_tenant__58ac31_idx'),
        ),
        migrations.AddIndex(
            model_name='rolepermission',
            index=models.Index(fields=['tenant', 'entity'], name='users_rolep_tenant__7f689e_idx'),
        ),
    ]
