"""Mock Google provider for testing and local development."""
from ..observability import byte_preview, get_logger, log_event, log_warning, safe_fields
from .fixtures import (
    MOCK_DOCX_BYTES,
    MOCK_PDF_BYTES,
    MOCK_PNG_BYTES,
    MOCK_PPTX_BYTES,
    MOCK_XLSX_BYTES,
    _corpus_bytes,
)
from .types import (
    GOOGLE_NATIVE_EXPORTS,
    AccountProfile,
    ClassroomActivity,
    ClassroomCourse,
    GoogleProvider,
    SubmissionFile,
    SubmissionGradeSummary,
    SubmissionLink,
    _grade_summary_from_submissions,
)


logger = get_logger(__name__)


class MockGoogleProvider(GoogleProvider):
    courses = [
        ClassroomCourse("course-1", "Biology 101", "Morning", "ACTIVE"),
        ClassroomCourse("course-2", "Literature Seminar", "Afternoon", "ACTIVE"),
        ClassroomCourse("course-archived", "Archived Algebra", None, "ARCHIVED"),
        ClassroomCourse("course-real", "Projetos Reais", "Turma Real", "ACTIVE"),
    ]

    activities = [
        ClassroomActivity("activity-1", "course-1", "Cell Diagram", "ASSIGNMENT", "PUBLISHED", "May 24"),
        ClassroomActivity(
            "activity-2",
            "course-1",
            "Lab Notes: Osmosis",
            "ASSIGNMENT",
            "PUBLISHED",
            "May 28",
            description="Record your osmosis observations.",
        ),
        ClassroomActivity(
            "activity-3",
            "course-2",
            "Essay Draft",
            "ASSIGNMENT",
            "PUBLISHED",
            "May 30",
            description=(
                "Write a persuasive essay of at least three paragraphs. State a clear "
                "thesis in the introduction, then support your argument with at least "
                "two pieces of textual evidence and explain how each one backs your "
                "claim. Close with a conclusion that restates the argument and its "
                "significance. You will be assessed on the strength of your thesis, the "
                "quality and integration of evidence, the clarity of your reasoning, and "
                "the organization and mechanics of your writing."
            ),
        ),
        ClassroomActivity(
            "activity-4",
            "course-2",
            "Projeto Final (multi-arquivo)",
            "ASSIGNMENT",
            "PUBLISHED",
            "Jun 5",
            description="Envie as duas partes do projeto como anexos.",
        ),
        ClassroomActivity(
            "activity-real",
            "course-real",
            "Trabalho Final de Programação",
            "ASSIGNMENT",
            "PUBLISHED",
            "Jun 28",
            description=(
                "Desenvolva um projeto de software completo. Entregue o código-fonte "
                "bem organizado, com documentação clara e exemplos de uso. O projeto "
                "será avaliado por lógica de programação, organização do código, "
                "completude da implementação e qualidade da documentação apresentada."
            ),
        ),
    ]

    graded_submission_ids = {
        "course-1": {
            "activity-1": {"export-file-1"},
            "activity-2": {"export-file-3"},
        }
    }

    def _mock_submission_id(self, file: SubmissionFile) -> str:
        return file.classroom_submission_id or file.id

    files = [
        SubmissionFile(
            "export-file-1",
            "course-1",
            "activity-1",
            "ana.silva@example.edu",
            "Ana Silva",
            "drive-file-1",
            "diagram.png",
            "image/png",
            MOCK_PNG_BYTES,
        ),
        SubmissionFile(
            "export-file-2",
            "course-1",
            "activity-1",
            "bruno.costa@example.edu",
            "Bruno Costa",
            "drive-file-2",
            "cell-diagram.gdoc",
            "application/vnd.google-apps.document",
            MOCK_PDF_BYTES,
        ),
        SubmissionFile(
            "export-file-3",
            "course-1",
            "activity-2",
            None,
            "Carla Mendes",
            "drive-file-3",
            "osmosis notes.pdf",
            "application/pdf",
            MOCK_PDF_BYTES,
        ),
        SubmissionFile(
            "export-file-4",
            "course-2",
            "activity-3",
            "diego.lima@example.edu",
            "Diego Lima",
            "drive-file-4",
            "essay draft.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            MOCK_DOCX_BYTES,
        ),
        SubmissionFile(
            "export-file-xlsx",
            "course-2",
            "activity-3",
            "elena.souza@example.edu",
            "Elena Souza",
            "drive-file-xlsx",
            "notas.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            MOCK_XLSX_BYTES,
        ),
        SubmissionFile(
            "export-file-pptx",
            "course-2",
            "activity-3",
            "fabio.melo@example.edu",
            "Fabio Melo",
            "drive-file-pptx",
            "apresentacao.pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            MOCK_PPTX_BYTES,
        ),
        # One student (Júlia) submits two attachments under a single Classroom
        # submission — they must collapse into one card graded as a set.
        SubmissionFile(
            "sub-julia:drive-file-5",
            "course-2",
            "activity-4",
            "julia.rocha@example.edu",
            "Júlia Rocha",
            "drive-file-5",
            "parte-1.txt",
            "text/plain",
            b"Parte 1: introducao do projeto final de Julia.\n",
            classroom_submission_id="sub-julia",
        ),
        SubmissionFile(
            "sub-julia:drive-file-6",
            "course-2",
            "activity-4",
            "julia.rocha@example.edu",
            "Júlia Rocha",
            "drive-file-6",
            "parte-2.txt",
            "text/plain",
            b"Parte 2: conclusao do projeto final de Julia.\n",
            classroom_submission_id="sub-julia",
        ),
        # --- course-real: real corpus files (guarded — content = b"" if missing) ---
        SubmissionFile(
            "real-file-docx",
            "course-real",
            "activity-real",
            "aluno.docx@escola.edu",
            "Aluno Documento",
            "real-drive-docx",
            "PIM_I_FINAL_CORRIGIDO.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            _corpus_bytes("submissions-office-suite/PIM_I_FINAL_CORRIGIDO.docx"),
        ),
        SubmissionFile(
            "real-file-html",
            "course-real",
            "activity-real",
            "aluno.html@escola.edu",
            "Aluno HTML",
            "real-drive-html",
            "index.html",
            "text/html",
            _corpus_bytes("submissions-code/tcc_golpe_zero/index.html"),
        ),
        SubmissionFile(
            "real-file-xlsx",
            "course-real",
            "activity-real",
            "aluno.xlsx@escola.edu",
            "Aluno Planilha",
            "real-drive-xlsx",
            "05 - FÓRMULAS E FUNÇÕES.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            _corpus_bytes("submissions-office-suite/05 - FÓRMULAS E FUNÇÕES.xlsx"),
        ),
        SubmissionFile(
            "real-file-pdf",
            "course-real",
            "activity-real",
            "aluno.pdf@escola.edu",
            "Aluno PDF",
            "real-drive-pdf",
            "PIM I - FINAL.pdf",
            "application/pdf",
            _corpus_bytes("submissions-office-suite/PIM I - FINAL.pdf"),
        ),
        SubmissionFile(
            "real-file-zip",
            "course-real",
            "activity-real",
            "aluno.zip@escola.edu",
            "Aluno ZIP",
            "real-drive-zip",
            "greenfit.zip",
            "application/zip",
            _corpus_bytes("submissions-code/greenfit.zip"),
        ),
    ]

    def account_profile(self) -> AccountProfile:
        profile = AccountProfile(
            name="Teacher Example",
            email="teacher@example.edu",
            picture=None,
        )
        log_event(logger, "mock.account_profile", profile=safe_fields(profile))
        return profile

    def get_course(self, course_id: str) -> ClassroomCourse:
        for course in self.courses:
            if course.id == course_id:
                log_event(logger, "mock.course.get", course=safe_fields(course))
                return course
        raise KeyError(course_id)

    def list_courses(self) -> list[ClassroomCourse]:
        log_event(logger, "mock.courses", count=len(self.courses), courses=[safe_fields(course) for course in self.courses])
        return self.courses

    def get_activity(self, course_id: str, activity_id: str) -> ClassroomActivity:
        for activity in self.activities:
            if activity.course_id == course_id and activity.id == activity_id:
                log_event(logger, "mock.activity.get", activity=safe_fields(activity))
                return activity
        raise KeyError(activity_id)

    def list_activities(self, course_id: str) -> list[ClassroomActivity]:
        rows = [activity for activity in self.activities if activity.course_id == course_id]
        log_event(logger, "mock.activities", course_id=course_id, count=len(rows), activities=[safe_fields(row) for row in rows])
        return rows

    def list_submission_files(
        self, course_id: str, activity_ids: list[str] | None = None
    ) -> list[SubmissionFile]:
        activity_filter = set(activity_ids or [])
        rows = [
            file
            for file in self.files
            if file.course_id == course_id
            and (not activity_filter or file.activity_id in activity_filter)
        ]
        log_event(
            logger,
            "mock.submission_files",
            course_id=course_id,
            activity_ids=activity_ids,
            count=len(rows),
            files=[safe_fields(row) for row in rows],
        )
        return rows

    def list_submission_links(
        self, course_id: str, activity_id: str
    ) -> list[SubmissionLink]:
        links = [
            SubmissionLink(
                source_file_id=file.source_file_id,
                classroom_submission_id=file.id,
                alternate_link=(
                    f"https://classroom.google.com/c/{course_id}/sm/{file.id}/details"
                ),
                student_email=file.student_email,
            )
            for file in self.files
            if file.course_id == course_id and file.activity_id == activity_id
        ]
        log_event(
            logger,
            "mock.submission_links",
            course_id=course_id,
            activity_id=activity_id,
            count=len(links),
            links=[safe_fields(link) for link in links],
        )
        return links

    def submission_grade_summary(
        self, course_id: str, activity_ids: list[str]
    ) -> dict[str, SubmissionGradeSummary]:
        summaries: dict[str, SubmissionGradeSummary] = {}
        for activity_id in activity_ids:
            submissions = [
                {
                    "id": self._mock_submission_id(file),
                    "assignedGrade": 100 if self._mock_submission_id(file) in self.graded_submission_ids.get(course_id, {}).get(activity_id, set()) else None,
                    "state": "RETURNED" if self._mock_submission_id(file) in self.graded_submission_ids.get(course_id, {}).get(activity_id, set()) else "TURNED_IN",
                }
                for file in self.files
                if file.course_id == course_id and file.activity_id == activity_id
            ]
            summaries[activity_id] = _grade_summary_from_submissions(submissions)
        log_event(
            logger,
            "mock.submission_grade_summary",
            course_id=course_id,
            activity_ids=activity_ids,
            summaries={key: safe_fields(value) for key, value in summaries.items()},
        )
        return summaries

    def ungraded_submission_ids(self, course_id: str, activity_id: str) -> set[str]:
        graded = self.graded_submission_ids.get(course_id, {}).get(activity_id, set())
        return {
            self._mock_submission_id(file)
            for file in self.files
            if file.course_id == course_id
            and file.activity_id == activity_id
            and self._mock_submission_id(file) not in graded
        }

    def get_file_content(self, file_id: str) -> tuple[bytes, str]:
        log_event(logger, "mock.file_content.start", file_id=file_id)
        for file in self.files:
            if file.id == file_id or file.source_file_id == file_id:
                export = GOOGLE_NATIVE_EXPORTS.get(file.mime_type)
                if export:
                    log_event(
                        logger,
                        "mock.file_content.complete",
                        file=safe_fields(file),
                        media_type=export[0],
                        byte_size=len(file.content),
                        byte_preview=byte_preview(file.content),
                    )
                    return file.content, export[0]
                log_event(
                    logger,
                    "mock.file_content.complete",
                    file=safe_fields(file),
                    media_type=file.mime_type,
                    byte_size=len(file.content),
                    byte_preview=byte_preview(file.content),
                )
                return file.content, file.mime_type
        log_warning(logger, "mock.file_content.missing", file_id=file_id)
        raise KeyError(file_id)
