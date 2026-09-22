import unittest

from student_model.student_profile import StudentProfile, classify_marks


class StudentClassificationTest(unittest.TestCase):
    def test_classify_marks_by_exam_score(self):
        self.assertEqual(classify_marks(92), 'Excellent')
        self.assertEqual(classify_marks(76), 'Good')
        self.assertEqual(classify_marks(60), 'Average')
        self.assertEqual(classify_marks(35), 'Needs Support')

    def test_profile_tracks_class_and_marks(self):
        profile = StudentProfile(
            student_id='s1',
            name='Asha',
            email='asha@example.com',
            class_name='BSc-CS-2025',
            exam_marks=81,
        )
        self.assertEqual(profile.class_name, 'BSc-CS-2025')
        self.assertEqual(profile.classification, 'Good')


if __name__ == '__main__':
    unittest.main()
