import io
import json
import unittest
import zipfile
from update_repository import GUID, catalog_package, inspect_package, version_key


class CatalogTests(unittest.TestCase):
    def package(self, **changes):
        meta = dict(guid=GUID, version='1.15.0.0', targetAbi='12.0.0.0', autoUpdate=False)
        meta.update(changes)
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as archive:
            archive.writestr('NeXroll.Jellyfin.dll', b'original-assembly')
            archive.writestr('thumb.png', b'original-thumbnail')
            archive.writestr('meta.json', json.dumps(meta))
        return output.getvalue()

    def test_enables_updates_without_changing_binary(self):
        blob = catalog_package(self.package(), '12.0.0.0', '1.15.0.0')
        meta, files = inspect_package(blob, '12.0.0.0', '1.15.0.0')
        self.assertTrue(meta['autoUpdate'])
        self.assertEqual(files['NeXroll.Jellyfin.dll'], b'original-assembly')
        self.assertEqual(files['thumb.png'], b'original-thumbnail')
        self.assertEqual(blob, catalog_package(self.package(), '12.0.0.0', '1.15.0.0'))

    def test_rejects_wrong_identity_version_or_abi(self):
        for changes in ({'guid': 'wrong'}, {'version': '1.14.0.0'}, {'targetAbi': '10.11.0.0'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                catalog_package(self.package(**changes), '12.0.0.0', '1.15.0.0')

    def test_rejects_bundled_host_libraries(self):
        output = io.BytesIO(self.package())
        with zipfile.ZipFile(output, 'a') as archive:
            archive.writestr('MediaBrowser.Common.dll', b'host-library')
        with self.assertRaises(ValueError):
            catalog_package(output.getvalue(), '12.0.0.0', '1.15.0.0')

    def test_numeric_version_order(self):
        self.assertGreater(version_key('1.15.0.0'), version_key('1.9.0.0'))
        with self.assertRaises(ValueError):
            version_key('1.15.0.0-beta')


if __name__ == '__main__':
    unittest.main()
