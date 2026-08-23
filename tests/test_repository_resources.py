import base64
import hashlib
import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
INDEX_PATH = ROOT / "repository.json"
RESOURCE_DIRECTORIES = {
    "device": "devices",
    "rgb-model": "models",
    "canvas": "canvases",
}
RESOURCE_SUFFIXES = {
    "device": ".mgdevice.json",
    "rgb-model": ".mgmodel.json",
    "canvas": ".mgcanvas.json",
}
RESOURCE_FILES = {
    "device": {
        "devices/vmax-320x960.mgdevice.json": "device-vmax-320x960",
        "devices/mythcool-480x480.mgdevice.json": "device-mythcool-480x480",
    },
    "rgb-model": {
        "models/rgb-led-strip-16.mgmodel.json": "rgb-led-strip-16",
        "models/rgb-led-strip-64.mgmodel.json": "rgb-led-strip-64",
    },
    "canvas": {
        "canvases/solid.mgcanvas.json": "canvas-solid",
        "canvases/rainbow.mgcanvas.json": "canvas-rainbow",
        "canvases/breathing.mgcanvas.json": "canvas-breathing",
        "canvases/wave.mgcanvas.json": "canvas-wave",
        "canvases/rainbow-rise.mgcanvas.json": "canvas-rainbow-rise",
    },
}
FORBIDDEN_KEYS = {
    "html", "javascript", "js", "script", "scripts", "wasm", "webassembly",
    "protocol", "protocolBytes", "usbPath", "devicePath", "comPort", "endpoint",
    "thirdParty", "vendorTemplate", "vendorAsset", "path", "filePath",
}
SAFE_RESOURCE_PATH = re.compile(
    r"^(devices|models|canvases)/[a-z0-9][a-z0-9-]*\.(mgdevice|mgmodel|mgcanvas)\.json$"
)
EXPECTED_EFFECT_PARAMETERS = {
    "static": {"color"},
    "rainbow": {"periodSeconds", "speed"},
    "breathing": {"color", "periodSeconds", "amplitude"},
    "wave": {"color", "periodSeconds", "wavelength", "speed"},
    "rainbowRise": {"centerX", "centerY", "spacing", "speed", "reverse", "periodSeconds"},
}


def load_signer():
    path = ROOT / "scripts" / "sign_repository.py"
    spec = importlib.util.spec_from_file_location("sign_repository", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RepositoryResourceTests(unittest.TestCase):
    def test_filesystem_matches_index_with_canonical_type_directories(self):
        index = json.loads(INDEX_PATH.read_text(encoding="ascii"))
        indexed_paths = {entry["downloadUrl"] for entry in index["resources"]}
        actual_paths = {
            path.relative_to(ROOT).as_posix()
            for directory in RESOURCE_DIRECTORIES.values()
            for path in (ROOT / directory).iterdir()
            if path.is_file()
        }
        self.assertEqual(indexed_paths, actual_paths)
        for entry in index["resources"]:
            path = entry["downloadUrl"]
            resource_type = entry["resourceType"]
            self.assertEqual(RESOURCE_DIRECTORIES[resource_type], path.split("/", 1)[0])
            self.assertTrue(path.endswith(RESOURCE_SUFFIXES[resource_type]), path)
            self.assertRegex(path, SAFE_RESOURCE_PATH.pattern)

    def test_all_expected_resource_documents_exist_with_safe_ascii_paths(self):
        for resource_type, expected in RESOURCE_FILES.items():
            for relative_path, resource_id in expected.items():
                self.assertRegex(relative_path, SAFE_RESOURCE_PATH.pattern)
                path = ROOT / relative_path
                self.assertTrue(path.is_file(), relative_path)
                raw = path.read_bytes()
                self.assertNotIn(b"\xef\xbb\xbf", raw)
                raw.decode("ascii")
                document = json.loads(raw)
                self.assertEqual(resource_id, document["resourceId"])
                self.assertEqual(1, document["schemaVersion"])
                self.assertEqual(resource_type, self.resource_type(document))
                self.assert_no_forbidden_keys(document)

    def test_index_payload_identity_version_schema_and_type_are_consistent(self):
        index = json.loads(INDEX_PATH.read_text(encoding="ascii"))
        resource_ids = []
        download_urls = []
        for entry in index["resources"]:
            resource_ids.append(entry["resourceId"])
            download_urls.append(entry["downloadUrl"])
            document = self.load(entry["downloadUrl"])
            self.assertEqual(entry["resourceId"], document["resourceId"])
            self.assertEqual(entry["version"], document["version"])
            self.assertEqual(1, document["schemaVersion"])
            self.assertEqual(entry["resourceType"], self.resource_type(document))
        self.assertEqual(len(resource_ids), len(set(resource_ids)))
        self.assertEqual(len(download_urls), len(set(download_urls)))

    def test_devices_declare_exact_host_profiles_and_verification(self):
        expected = {
            "device-vmax-320x960": ("33C3", "F101", 320, 960, "vmax-jpeg"),
            "device-mythcool-480x480": ("374A", "A005", 480, 480, "mythcool-rgb565"),
        }
        for relative_path in RESOURCE_FILES["device"]:
            document = self.load(relative_path)
            profile = document["profile"]
            self.assertEqual(expected[document["resourceId"]], (
                profile["vendorId"], profile["productId"], profile["resolution"]["width"],
                profile["resolution"]["height"], profile["driver"]["kind"]
            ))
            self.assertIsInstance(profile["verification"], dict)
            self.assertTrue(profile["verification"]["hardwareVerified"])
            self.assertEqual(0, profile["interfaceNumber"])
            self.assertNotIn("comPort", profile)

    def test_models_use_bounded_bijective_mapping_and_coordinates(self):
        for relative_path in RESOURCE_FILES["rgb-model"]:
            document = self.load(relative_path)
            model = document["model"]
            led_count = model["ledCount"]
            width = model["width"]
            height = model["height"]
            self.assertIsInstance(led_count, int)
            self.assertGreater(led_count, 0)
            self.assertIsInstance(width, int)
            self.assertIsInstance(height, int)
            self.assertGreater(width, 0)
            self.assertGreater(height, 0)
            self.assertEqual(led_count, len(model["coordinates"]))
            self.assertEqual(led_count, len(model["mapping"]))
            self.assertEqual(set(range(led_count)), set(model["mapping"]))
            self.assertTrue(all(isinstance(value, int) for value in model["mapping"]))
            for point in model["coordinates"]:
                self.assertEqual(2, len(point))
                self.assertTrue(all(isinstance(value, (int, float)) for value in point))
                self.assertGreaterEqual(point[0], 0)
                self.assertLess(point[0], width)
                self.assertGreaterEqual(point[1], 0)
                self.assertLess(point[1], height)

    def test_canvases_validate_complete_effect_parameters_and_geometry(self):
        expected_kinds = {
            "canvas-solid": "static",
            "canvas-rainbow": "rainbow",
            "canvas-breathing": "breathing",
            "canvas-wave": "wave",
            "canvas-rainbow-rise": "rainbowRise",
        }
        for relative_path in RESOURCE_FILES["canvas"]:
            document = self.load(relative_path)
            canvas = document["canvas"]
            self.assertEqual(2, canvas["schemaVersion"])
            self.assertGreater(canvas["canvas"]["width"], 0)
            self.assertGreater(canvas["canvas"]["height"], 0)
            canvas_width = canvas["canvas"]["width"]
            canvas_height = canvas["canvas"]["height"]
            self.assertTrue(canvas["components"])
            for component in canvas["components"]:
                screen = component["screen"]
                self.assertGreater(screen["width"], 0)
                self.assertGreater(screen["height"], 0)
                self.assertGreaterEqual(screen["x"], 0)
                self.assertGreaterEqual(screen["y"], 0)
                self.assertLessEqual(screen["x"] + screen["width"], canvas_width)
                self.assertLessEqual(screen["y"] + screen["height"], canvas_height)
            self.assertEqual("all-compatible", document["targets"]["mode"])
            effect = document["effect"]
            self.assertEqual(expected_kinds[document["resourceId"]], effect["kind"])
            parameters = effect["parameters"]
            self.assertEqual(EXPECTED_EFFECT_PARAMETERS[effect["kind"]], set(parameters))
            self.assert_effect_parameters_are_safe(effect["kind"], parameters)

    def test_index_resources_have_hashes_and_development_signatures_are_explicit(self):
        index = json.loads(INDEX_PATH.read_text(encoding="ascii"))
        self.assertEqual([], index["packages"])
        entries = index["resources"]
        self.assertEqual(9, len(entries))
        self.assertEqual(set(sum((list(items.values()) for items in RESOURCE_FILES.values()), [])),
                         {entry["resourceId"] for entry in entries})
        for entry in entries:
            self.assertIn(entry["resourceType"], RESOURCE_FILES)
            self.assertIn(entry["downloadUrl"], RESOURCE_FILES[entry["resourceType"]])
            self.assertEqual(entry["resourceId"], RESOURCE_FILES[entry["resourceType"]][entry["downloadUrl"]])
            payload = (ROOT / entry["downloadUrl"]).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), entry["sha256"])
            self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")
            for field in ("resourceId", "resourceType", "version", "downloadUrl", "sha256", "minHostVersion", "signature"):
                self.assertTrue(entry[field], field)
            self.assertEqual("TEST-SIGNATURE-PENDING-OFFICIAL-RELEASE", entry["signature"])

    def test_release_verifier_rejects_pending_signatures_before_key_use(self):
        signer = load_signer()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "repository.json").write_text(json.dumps({
                "schemaVersion": 1,
                "repositoryId": "official",
                "packages": [],
                "resources": [{"downloadUrl": "canvases/demo.mgcanvas.json", "signature": "TEST-SIGNATURE-PENDING-OFFICIAL-RELEASE"}],
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "placeholder"):
                signer.verify_release_artifacts(root, root / "public.pem")

    def assert_effect_parameters_are_safe(self, kind, parameters):
        def assert_color(color):
            self.assertIsInstance(color, dict)
            self.assertEqual({"r", "g", "b"}, set(color))
            for channel in color.values():
                self.assertIsInstance(channel, int)
                self.assertGreaterEqual(channel, 0)
                self.assertLessEqual(channel, 255)

        if kind == "static":
            assert_color(parameters["color"])
        elif kind == "breathing":
            assert_color(parameters["color"])
            self.assertGreater(parameters["periodSeconds"], 0)
            self.assertGreater(parameters["amplitude"], 0)
            self.assertLessEqual(parameters["amplitude"], 1)
        elif kind == "wave":
            assert_color(parameters["color"])
            self.assertGreater(parameters["periodSeconds"], 0)
            self.assertGreater(parameters["wavelength"], 0)
            self.assertGreater(parameters["speed"], 0)
        elif kind == "rainbow":
            self.assertGreater(parameters["periodSeconds"], 0)
            self.assertGreater(parameters["speed"], 0)
        elif kind == "rainbowRise":
            self.assertIsInstance(parameters["centerX"], (int, float))
            self.assertIsInstance(parameters["centerY"], (int, float))
            self.assertGreater(parameters["spacing"], 0)
            self.assertGreater(parameters["speed"], 0)
            self.assertIsInstance(parameters["reverse"], bool)
            self.assertGreater(parameters["periodSeconds"], 0)

    def load(self, relative_path):
        return json.loads((ROOT / relative_path).read_text(encoding="ascii"))

    @staticmethod
    def resource_type(document):
        if "profile" in document:
            return "device"
        if "model" in document:
            return "rgb-model"
        if "effect" in document:
            return "canvas"
        return None

    def assert_no_forbidden_keys(self, value):
        if isinstance(value, dict):
            self.assertTrue(FORBIDDEN_KEYS.isdisjoint(value.keys()), sorted(set(value) & FORBIDDEN_KEYS))
            for child in value.values():
                self.assert_no_forbidden_keys(child)
        elif isinstance(value, list):
            for child in value:
                self.assert_no_forbidden_keys(child)


if __name__ == "__main__":
    unittest.main()
