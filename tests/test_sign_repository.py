import base64
import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "sign_repository.py"


def load_signer():
    spec = importlib.util.spec_from_file_location("sign_repository", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SignedRepositoryTests(unittest.TestCase):
    def test_signing_is_verifiable_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packages = root / "packages"
            packages.mkdir()
            package = packages / "demo.mgpack.json"
            package.write_bytes(b'{"schemaVersion":1}\n')
            (root / "repository.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "repositoryId": "official",
                        "name": "Official",
                        "publisher": "Test",
                        "packages": [
                            {
                                "packageId": "demo",
                                "version": "1.0.0",
                                "downloadUrl": "packages/demo.mgpack.json",
                                "sha256": "0" * 64,
                                "minHostVersion": "1.0.0",
                                "signature": "",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            private_key = root / "private.pem"
            public_key = root / "public.pem"
            subprocess.run(
                ["openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", str(private_key)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                ["openssl", "pkey", "-in", str(private_key), "-pubout", "-out", str(public_key)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.run_sign(root, private_key)
            first_index = (root / "repository.json").read_bytes()
            first_signature = (root / "repository.json.sig").read_bytes()
            self.assertTrue(first_signature.strip())
            entry = json.loads(first_index)["packages"][0]
            self.assertEqual(entry["sha256"], hashlib.sha256(package.read_bytes()).hexdigest())
            package_signature = base64.b64decode(entry["signature"], validate=True)
            self.assertTrue(package_signature)
            self.assert_verified(public_key, package, package_signature)
            self.assert_verified_bytes(public_key, root / "repository.json", base64.b64decode(first_signature.strip(), validate=True))
            load_signer().verify_release_artifacts(root, public_key)
            verify_result = subprocess.run(
                [
                    "python",
                    str(SCRIPT),
                    "--repository-root",
                    str(root),
                    "--verify-release",
                    "--public-key",
                    str(public_key),
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(verify_result.returncode, 0, verify_result.stderr.decode())

            self.run_sign(root, private_key)
            self.assertEqual(first_index, (root / "repository.json").read_bytes())
            self.assertEqual(first_signature, (root / "repository.json.sig").read_bytes())

    def test_signing_updates_resource_hashes_and_signatures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resource = root / "canvases" / "demo.mgcanvas.json"
            resource.parent.mkdir()
            resource.write_bytes(b'{"schemaVersion":1}\n')
            (root / "repository.json").write_text(
                json.dumps({
                    "schemaVersion": 1,
                    "repositoryId": "official",
                    "name": "Official",
                    "publisher": "Test",
                    "packages": [],
                    "resources": [{
                        "resourceId": "canvas-demo",
                        "resourceType": "canvas",
                        "version": "1.0.0",
                        "downloadUrl": "canvases/demo.mgcanvas.json",
                        "sha256": "0" * 64,
                        "minHostVersion": "1.0.0",
                        "signature": "",
                    }],
                }),
                encoding="utf-8",
            )
            private_key = root / "private.pem"
            public_key = root / "public.pem"
            subprocess.run(
                ["openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", str(private_key)],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            subprocess.run(
                ["openssl", "pkey", "-in", str(private_key), "-pubout", "-out", str(public_key)],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )

            self.run_sign(root, private_key)
            index = json.loads((root / "repository.json").read_text(encoding="utf-8"))
            entry = index["resources"][0]
            self.assertEqual(hashlib.sha256(resource.read_bytes()).hexdigest(), entry["sha256"])
            signature = base64.b64decode(entry["signature"], validate=True)
            self.assert_verified(public_key, resource, signature)
            load_signer().verify_release_artifacts(root, public_key)

    def test_rejects_resource_path_matrix_without_writing_signature(self):
        signer = load_signer()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resource = root / "canvases" / "demo.mgcanvas.json"
            resource.parent.mkdir()
            resource.write_bytes(b"{}")
            cases = [
                ("../canvases/demo.mgcanvas.json", "canvas"),
                ("canvases/../demo.mgcanvas.json", "canvas"),
                ("canvases//demo.mgcanvas.json", "canvas"),
                ("canvases/./demo.mgcanvas.json", "canvas"),
                ("/canvases/demo.mgcanvas.json", "canvas"),
                ("https://example.invalid/demo.mgcanvas.json", "canvas"),
                ("canvases/demo.mgcanvas.json?x=1", "canvas"),
                ("canvases/demo.mgcanvas.json#fragment", "canvas"),
                ("canvases/%2e%2e/demo.mgcanvas.json", "canvas"),
                ("canvases/%252e%252e/demo.mgcanvas.json", "canvas"),
                ("models/demo.mgcanvas.json", "canvas"),
                ("canvases/demo.mgmodel.json", "canvas"),
            ]
            for path, resource_type in cases:
                with self.subTest(path=path):
                    with self.assertRaises(ValueError):
                        signer.resolve_resource(root, path, resource_type)
                    self.assertFalse((root / "repository.json.sig").exists())

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "repository.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "repositoryId": "official",
                        "name": "Official",
                        "publisher": "Test",
                        "packages": [
                            {
                                "packageId": "bad",
                                "version": "1.0.0",
                                "downloadUrl": "../bad.mgpack.json",
                                "sha256": "0" * 64,
                                "minHostVersion": "1.0.0",
                                "signature": "",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            private_key = root / "private.pem"
            subprocess.run(
                ["openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", str(private_key)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            result = subprocess.run(
                ["python", str(SCRIPT), "--repository-root", str(root), "--private-key", str(private_key)],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / "repository.json.sig").exists())

    @staticmethod
    def run_sign(root: Path, private_key: Path) -> None:
        subprocess.run(
            ["python", str(SCRIPT), "--repository-root", str(root), "--private-key", str(private_key)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    @staticmethod
    def assert_verified(public_key: Path, payload: Path, signature: bytes) -> None:
        with tempfile.TemporaryDirectory(prefix="mg-signature-test-") as directory:
            signature_file = Path(directory) / "signature"
            signature_file.write_bytes(signature)
            subprocess.run(
                [
                    "openssl",
                    "dgst",
                    "-sha256",
                    "-verify",
                    str(public_key),
                    "-signature",
                    str(signature_file),
                    str(payload),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    @classmethod
    def assert_verified_bytes(cls, public_key: Path, payload: Path, signature: bytes) -> None:
        cls.assert_verified(public_key, payload, signature)


if __name__ == "__main__":
    unittest.main()
