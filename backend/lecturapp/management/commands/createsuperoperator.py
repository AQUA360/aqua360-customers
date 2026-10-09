from django.core.management.base import BaseCommand
from lecturapp.models import ReadingOperator

class Command(BaseCommand):
    help = 'Create a super operator for lecturapp'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, required=True, help='Username for the operator')
        parser.add_argument('--password', type=str, required=True, help='Password for the operator')
        parser.add_argument('--name', type=str, required=True, help='First name of the operator')
        parser.add_argument('--surname', type=str, required=True, help='Last name of the operator')

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        name = options['name']
        surname = options['surname']

        # Check if operator already exists
        if ReadingOperator.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.ERROR(f'Operator with username "{username}" already exists.')
            )
            return

        # Create the operator
        operator = ReadingOperator.objects.create(
            username=username,
            name=name,
            surname=surname,
            is_active=True
        )
        operator.set_password(password)
        operator.save()

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created operator "{name} {surname}" with username "{username}"'
            )
        ) 