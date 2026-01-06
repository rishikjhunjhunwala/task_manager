"""
Management command to set up Django-Q2 schedules for notification jobs.

This command creates/updates the scheduled tasks required for:
- Hourly deadline reminder checks
- Daily overdue task notifications (9:00 AM IST)
- Daily dashboard email summaries (8:00 AM IST)

Usage:
    python manage.py setup_schedules

The command is idempotent - safe to run multiple times.
Existing schedules will be updated if their configuration changes.
"""
from django.core.management.base import BaseCommand
from django_q.models import Schedule


class Command(BaseCommand):
    help = 'Set up Django-Q2 schedules for notification jobs'

    def handle(self, *args, **options):
        self.stdout.write('\nSetting up Django-Q2 schedules...\n')
        
        schedules_created = 0
        schedules_updated = 0
        
        # Schedule 1: Deadline Reminder Check - Runs every hour
        # Checks for tasks with deadlines approaching in the next 24 hours
        schedule_1, created = Schedule.objects.update_or_create(
            name='Deadline Reminder Check',
            defaults={
                'func': 'apps.notifications.tasks.check_deadline_reminders',
                'schedule_type': Schedule.HOURLY,
                'repeats': -1,  # Run forever
            }
        )
        if created:
            schedules_created += 1
            self.stdout.write(
                self.style.SUCCESS('✓ Created schedule: Deadline Reminder Check (hourly)')
            )
        else:
            schedules_updated += 1
            self.stdout.write(
                self.style.WARNING('↻ Updated schedule: Deadline Reminder Check (hourly)')
            )
        
        # Schedule 2: Overdue Task Check - Runs daily at 9:00 AM IST
        # Sends daily reminders for overdue tasks and handles escalation
        schedule_2, created = Schedule.objects.update_or_create(
            name='Overdue Task Check',
            defaults={
                'func': 'apps.notifications.tasks.check_overdue_tasks',
                'schedule_type': Schedule.CRON,
                'cron': '0 9 * * *',  # 9:00 AM daily
                'repeats': -1,  # Run forever
            }
        )
        if created:
            schedules_created += 1
            self.stdout.write(
                self.style.SUCCESS('✓ Created schedule: Overdue Task Check (daily at 9:00 AM)')
            )
        else:
            schedules_updated += 1
            self.stdout.write(
                self.style.WARNING('↻ Updated schedule: Overdue Task Check (daily at 9:00 AM)')
            )
        
        # Schedule 3: Daily Dashboard Email - Runs daily at 8:00 AM IST
        # Sends task summary emails to all active users with pending tasks
        schedule_3, created = Schedule.objects.update_or_create(
            name='Daily Dashboard Email',
            defaults={
                'func': 'apps.notifications.tasks.send_daily_dashboard_emails',
                'schedule_type': Schedule.CRON,
                'cron': '0 8 * * *',  # 8:00 AM daily
                'repeats': -1,  # Run forever
            }
        )
        if created:
            schedules_created += 1
            self.stdout.write(
                self.style.SUCCESS('✓ Created schedule: Daily Dashboard Email (daily at 8:00 AM)')
            )
        else:
            schedules_updated += 1
            self.stdout.write(
                self.style.WARNING('↻ Updated schedule: Daily Dashboard Email (daily at 8:00 AM)')
            )
        
        # Summary
        total = schedules_created + schedules_updated
        self.stdout.write('')
        
        if schedules_created > 0 and schedules_updated > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Done! {schedules_created} schedule(s) created, '
                    f'{schedules_updated} schedule(s) updated. '
                    f'Total: {total} schedules configured.'
                )
            )
        elif schedules_created > 0:
            self.stdout.write(
                self.style.SUCCESS(f'Done! {schedules_created} schedules configured.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Done! All {total} schedules already exist and were updated.'
                )
            )
        
        self.stdout.write('')
        self.stdout.write('Schedule Summary:')
        self.stdout.write('  • Deadline Reminder Check  → Runs every hour')
        self.stdout.write('  • Overdue Task Check       → Runs daily at 9:00 AM IST')
        self.stdout.write('  • Daily Dashboard Email    → Runs daily at 8:00 AM IST')
        self.stdout.write('')
        self.stdout.write(
            self.style.NOTICE(
                'Note: Ensure Django-Q cluster is running: python manage.py qcluster'
            )
        )
        self.stdout.write('')