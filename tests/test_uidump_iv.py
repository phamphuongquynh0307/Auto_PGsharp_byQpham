import unittest

from avc import uidump


def encounter_xml(resource_suffix: str, text: str) -> str:
    return (
        '<hierarchy><node resource-id="com.nianticlabs.pokemongo:id/'
        f'hl_ec_sum_{resource_suffix}" text="{text}" bounds="[0,0][100,50]" />'
        '</hierarchy>'
    )


class EncounterIvTests(unittest.TestCase):
    def test_reads_semantic_special_background_icon_without_caring_about_artwork(self):
        xml = encounter_xml("stats", "12/10/11").replace(
            "</hierarchy>",
            '<node resource-id="com.nianticlabs.pokemongo:id/hl_ec_sum_special_bg" '
            'class="android.widget.ImageView" bounds="[700,500][740,540]" />'
            "</hierarchy>",
        )

        self.assertTrue(uidump.parse(xml).special_background)

    def test_reads_bare_percentage_from_iv_field(self):
        state = uidump.parse(encounter_xml("iv", "98%"))
        self.assertEqual(98, state.iv_percent)

    def test_reads_compact_iv_label(self):
        state = uidump.parse(encounter_xml("value", "IV96"))
        self.assertEqual(96, state.iv_percent)

    def test_derives_display_percentage_from_stat_triplet(self):
        state = uidump.parse(encounter_xml("stats", "15/15/14"))
        self.assertEqual((15, 15, 14), state.iv_stats)
        self.assertEqual(98, state.iv_percent)

    def test_derives_percentage_from_three_separate_stat_fields(self):
        xml = (
            '<hierarchy>'
            '<node resource-id="x:id/hl_ec_sum_atk" text="15" bounds="[0,0][1,1]" />'
            '<node resource-id="x:id/hl_ec_sum_def" text="15" bounds="[0,0][1,1]" />'
            '<node resource-id="x:id/hl_ec_sum_sta" text="14" bounds="[0,0][1,1]" />'
            '</hierarchy>'
        )
        state = uidump.parse(xml)
        self.assertEqual((15, 15, 14), state.iv_stats)
        self.assertEqual(98, state.iv_percent)

    def test_same_percentage_keeps_different_columns_distinct(self):
        first = uidump.parse(encounter_xml("stats", "15/15/14"))
        second = uidump.parse(encounter_xml("stats", "14/15/15"))
        self.assertEqual(first.iv_percent, second.iv_percent)
        self.assertNotEqual(first.iv_stats, second.iv_stats)

    def test_does_not_mistake_level_for_iv(self):
        state = uidump.parse(encounter_xml("level", "40"))
        self.assertIsNone(state.iv_percent)

    def test_reads_alternate_unicode_triplet_separators(self):
        state = uidump.parse(encounter_xml("stats", "15／14／13"))
        self.assertEqual((15, 14, 13), state.iv_stats)

    def test_reads_labelled_stats_instead_of_assuming_number_order(self):
        state = uidump.parse(encounter_xml("details", "HP 13  ATK: 15  Defense=14"))
        self.assertEqual((15, 14, 13), state.iv_stats)

    def test_reads_three_anonymous_children_of_encounter_container(self):
        xml = (
            '<hierarchy><node resource-id="x:id/hl_ec_summary" text="" '
            'bounds="[0,0][100,100]">'
            '<node resource-id="" text="15" bounds="[0,0][10,10]" />'
            '<node resource-id="" text="14" bounds="[10,0][20,10]" />'
            '<node resource-id="" text="13" bounds="[20,0][30,10]" />'
            '</node></hierarchy>'
        )
        state = uidump.parse(xml)
        self.assertEqual((15, 14, 13), state.iv_stats)

    def test_reads_shorter_encounter_resource_names_and_content_descriptions(self):
        xml = (
            '<hierarchy>'
            '<node resource-id="x:id/hl_ec_atk" text="" content-desc="15" '
            'bounds="[0,0][1,1]" />'
            '<node resource-id="x:id/hl_ec_def" text="14" bounds="[0,0][1,1]" />'
            '<node resource-id="x:id/hl_ec_hp" text="13" bounds="[0,0][1,1]" />'
            '</hierarchy>'
        )
        state = uidump.parse(xml)
        self.assertEqual((15, 14, 13), state.iv_stats)


if __name__ == "__main__":
    unittest.main()
