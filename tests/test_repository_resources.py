import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
INDEX_PATH = ROOT / "repository.json"
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
SAFE_RELATIVE_PATH = re.compile(r"^(devices|models|canvases)/[a-z0-9][a-z0-9-]*\.(mgdevice|mgmodel|mgcanvas)\.json$")


class RepositoryResourceTests(unittest.TestCase):
    def test_all_expected_resource_documents_exist_with_safe_ascii_paths(self):
        for resource_type, expected in RESOURCE_FILES.items():
            for relative_path, resource_id in expected.items():
                self.assertRegex(relative_path, SAFE_RELATIVE_PATH.pattern)
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

    def test_models_are_self_authored_coordinate_and_mapping_data(self):
        for relative_path in RESOURCE_FILES["rgb-model"]:
            document = self.load(relative_path)
            model = document["model"]
            self.assertEqual("MagicalGirlCaseMirror", document["publisher"])
            self.assertEqual(model["ledCount"], len(model["coordinates"]))
            self.assertEqual(model["ledCount"], len(model["mapping"]))
            self.assertEqual(list(range(model["ledCount"])), model["mapping"])
            self.assertTrue(all(len(point) == 2 for point in model["coordinates"]))
            self.assertTrue(all(isinstance(value, (int, float)) for point in model["coordinates"] for value in point))

    def test_canvases_use_supported_declarative_effects_and_dimensions(self):
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
            self.assertIn(canvas["schemaVersion"], (1, 2))
            self.assertGreater(canvas["canvas"]["width"], 0)
            self.assertGreater(canvas["canvas"]["height"], 0)
            self.assertEqual("all-compatible", document["targets"]["mode"])
            effect = document["effect"]
            self.assertEqual(expected_kinds[document["resourceId"]], effect["kind"])
            self.assertIsInstance(effect["parameters"], dict)
            if effect["kind"] == "static":
                self.assertEqual({"color"}, set(effect["parameters"]))
            if effect["kind"] == "rainbow":
                self.assertTrue({"periodSeconds", "speed"}.issubset(effect["parameters"]))

    def test_index_resources_use_valid_signature_encoding_or_test_placeholder(self):
        index = json.loads(INDEX_PATH.read_text(encoding="ascii"))
        for entry in index["resources"]:
            signature = entry["signature"]
            self.assertTrue(
                signature == "TEST-SIGNATURE-PENDING-OFFICIAL-RELEASE"
                or re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", signature)
            )

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
