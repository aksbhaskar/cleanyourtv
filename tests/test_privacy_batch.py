"""Read-only audit bundles preserve individual command output and attribution."""
import subprocess
import unittest
from unittest import mock

from tools import privacy


class FakeTV:
    def __init__(self, count, malformed=None, old=False):
        self.names = [f"com.example.voice{i}" for i in range(count)]
        self.calls = []
        self.malformed = malformed
        self.old = old

    def shell(self, command, read_timeout_s=None):
        self.calls.append(command)
        if command.startswith("pm list packages"):
            if "-d" in command:
                return "package:" + self.names[-1] if self.names else ""
            if self.old and "--user" in command:
                return "Error: unknown option --user"
            return "\n".join("package:" + name for name in self.names + ["com.example.plain"])
        functions = r'''
settings() {
    case "$3" in
        assistant) printf 'com.example.voice0/.Assistant\n';;
        voice_recognition_service) printf 'Error: permission denied\n' >&2; return 1;;
        *) printf 'null\n';;
    esac
}
dumpsys() {
    case "$2" in
        *voice1) printf 'Error: package unavailable\n' >&2; return 1;;
        *voice2) return 0;;
        *voice3) printf 'userId=1000\n';;
        *) printf 'appId=10123\nrequested permissions:\n  android.permission.RECORD_AUDIO\n';;
    esac
}
appops() {
    case "$2" in
        *voice0) printf 'RECORD_AUDIO: allow; time=+1s ago\n';;
        *voice1) printf 'Error: denied\n' >&2; return 1;;
        *voice2) return 0;;
        *) printf 'No operations.\n';;
    esac
}
'''
        result = subprocess.run(["sh", "-c", functions + command], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, timeout=5)
        output = result.stdout
        if "CYTV_" in command and self.malformed:
            if self.malformed == "truncated":
                return output[:len(output) // 2]
            if self.malformed == "unmarked":
                return "Error: unsupported shell syntax"
            return output + "\nunexpected trailing output"
        return output


class PrivacyBatchTest(unittest.TestCase):
    def test_stderr_and_whitespace_match_individual_shell_reads(self):
        commands = ["printf '  stdout before\\n'; printf 'stderr\\n' >&2; "
                    "printf 'stdout after  '",
                    "printf '  stderr only  ' >&2; false", "true"]
        expected = [privacy.shell(FakeTV(0), command) for command in commands]
        self.assertEqual(expected, ["stdout before\nstderr\nstdout after", "stderr only", ""])
        self.assertEqual(privacy.read_bundle(FakeTV(0), commands), expected)

    def individual_audit(self, device):
        with mock.patch.object(privacy, "read_bundle",
                               lambda dev, commands: [privacy.shell(dev, cmd) for cmd in commands]):
            return privacy.audit(device)

    def test_call_counts_and_reports_match_individual_reads(self):
        for count, before, after in ((10, 25, 5), (25, 55, 8), (0, 5, 3)):
            with self.subTest(count=count):
                individual = FakeTV(count)
                expected = self.individual_audit(individual)
                bundled = FakeTV(count)
                self.assertEqual(privacy.audit(bundled), expected)
                self.assertEqual(len(individual.calls), before)
                self.assertEqual(len(bundled.calls), after)
                for command in bundled.calls:
                    self.assertNotIn("disable", command)
                    self.assertLessEqual(command.count("dumpsys package"), 5)
                self.assertEqual(bundled.calls[:2], ["pm list packages --user 0",
                                                    "pm list packages -d --user 0"])

    def test_malformed_bundles_fall_back_without_misattributing_errors(self):
        expected = self.individual_audit(FakeTV(10))
        for malformed in ("truncated", "unmarked", "trailing"):
            with self.subTest(malformed=malformed):
                device = FakeTV(10, malformed=malformed)
                self.assertEqual(privacy.audit(device), expected)
                self.assertEqual(len(device.calls), 28)

    def test_old_firmware_keeps_unscoped_fallback(self):
        device = FakeTV(10, old=True)
        self.assertEqual(privacy.audit(device), self.individual_audit(FakeTV(10, old=True)))
        self.assertEqual(device.calls[:3], ["pm list packages --user 0", "pm list packages",
                                           "pm list packages -d"])

    def test_transport_errors_are_not_hidden(self):
        device = mock.Mock()
        device.shell.side_effect = ConnectionError("disconnected")
        with self.assertRaisesRegex(ConnectionError, "disconnected"):
            privacy.read_bundle(device, ["settings get secure assistant"])


if __name__ == "__main__":
    unittest.main()
