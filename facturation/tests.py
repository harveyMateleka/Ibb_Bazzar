from django.test import SimpleTestCase

from facturation.impression import _ligne_detail, _montant_compact


class RecuLigneTests(SimpleTestCase):
    def test_detail_tient_sur_une_ligne(self):
        ligne = _ligne_detail('Capitaine grillé', 1, '22000', '22000')
        self.assertEqual(ligne.count('\n'), 0)
        self.assertIn('Capitaine grillé', ligne)
        self.assertRegex(ligne, r'1\s+22000\s+22000')
        self.assertLessEqual(len(ligne), 42)

    def test_montant_sans_decimales_inutiles(self):
        self.assertEqual(_montant_compact('22000.00'), '22000')
        self.assertEqual(_montant_compact('10.50'), '10.5')
