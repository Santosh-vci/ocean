from django.core.management.base import BaseCommand

from apps.telemetry.replay import seed_phase3_replay_runs


class Command(BaseCommand):
    help = "Seed deterministic Phase 3 synthetic replay runs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--preserve-status",
            action="store_true",
            help="Keep current replay status/timestamps instead of resetting to draft.",
        )

    def handle(self, *args, **options):
        runs = seed_phase3_replay_runs(reset_status=not options["preserve_status"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(runs)} Phase 3 replay runs."
            )
        )
