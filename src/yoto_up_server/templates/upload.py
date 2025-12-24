"""
Upload templates.
"""

from typing import List

from pydom import Component
from pydom import html as d

from yoto_up_server.models import UploadJob, UploadStatus


class UploadPage(Component):
    """Upload page content."""
    
    def render(self):
        return d.Div()(
            d.H1(classes="text-2xl font-bold text-gray-900 mb-2")("Upload Audio"),
            d.P(classes="text-gray-600 mb-8")("Upload audio files to create or update Yoto cards."),
            
            # Upload form
            d.Div(classes="bg-white shadow sm:rounded-lg mb-8")(
                d.Div(classes="px-4 py-5 sm:p-6")(
                    d.Form(
                        hx_post="/upload/files",
                        hx_target="#upload-queue",
                        hx_encoding="multipart/form-data",
                        hx_indicator="#upload-loading",
                    )(
                        # File drop zone
                        d.Div(
                            id="drop-zone",
                            classes="mt-1 flex justify-center px-6 pt-5 pb-6 border-2 border-gray-300 border-dashed rounded-md hover:border-indigo-500 transition-colors cursor-pointer bg-gray-50 hover:bg-gray-100"
                        )(
                            d.Div(classes="space-y-1 text-center")(
                                d.Div(classes="mx-auto h-12 w-12 text-gray-400 text-4xl")("📁"),
                                d.Div(classes="flex text-sm text-gray-600")(
                                    d.Label(
                                        html_for="file-input",
                                        classes="relative cursor-pointer bg-white rounded-md font-medium text-indigo-600 hover:text-indigo-500 focus-within:outline-none focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-indigo-500 px-2"
                                    )(
                                        d.Span()("Upload files"),
                                        d.Input(
                                            type="file",
                                            name="files",
                                            id="file-input",
                                            multiple=True,
                                            accept="audio/*",
                                            classes="sr-only",
                                            onchange="this.form.requestSubmit()"
                                        ),
                                    ),
                                    d.P(classes="pl-1")("or drag and drop"),
                                ),
                                d.P(classes="text-xs text-gray-500")("MP3, M4A, WAV up to 100MB"),
                            ),
                        ),
                    ),
                ),
            ),
            
            # Loading indicator
            d.Div(id="upload-loading", classes="htmx-indicator flex items-center justify-center space-x-2 py-4")(
                d.Div(classes="animate-spin h-5 w-5 border-2 border-indigo-500 rounded-full border-t-transparent"),
                d.Span(classes="text-gray-500")("Uploading files..."),
            ),
            
            # Upload queue
            d.Div(classes="mb-8")(
                d.H2(classes="text-lg font-medium text-gray-900 mb-4")("Upload Queue"),
                d.Div(
                    id="upload-queue",
                    hx_get="/upload/queue",
                    hx_trigger="load",
                    classes="bg-white shadow overflow-hidden sm:rounded-md"
                ),
            ),
            
            # Upload options
            d.Div(classes="bg-white shadow sm:rounded-lg")(
                d.Div(classes="px-4 py-5 sm:px-6 border-b border-gray-200")(
                    d.H3(classes="text-lg leading-6 font-medium text-gray-900")("Processing Options"),
                ),
                d.Div(classes="px-4 py-5 sm:p-6")(
                    d.Form(
                        hx_post="/upload/process",
                        hx_target="#process-status",
                    )(
                        d.Div(classes="grid grid-cols-1 gap-y-6 gap-x-4 sm:grid-cols-6")(
                            d.Div(classes="sm:col-span-3")(
                                d.Label(html_for="upload-target", classes="block text-sm font-medium text-gray-700")("Target"),
                                d.Select(
                                    name="target",
                                    id="upload-target",
                                    classes="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
                                )(
                                    d.Option(value="new")("Create New Card"),
                                    d.Option(value="existing")("Add to Existing Card"),
                                ),
                            ),
                            d.Div(classes="sm:col-span-3")(
                                d.Label(html_for="card-title", classes="block text-sm font-medium text-gray-700")("Card Title"),
                                d.Input(
                                    type="text",
                                    name="title",
                                    id="card-title",
                                    placeholder="Enter title for new card...",
                                    classes="mt-1 focus:ring-indigo-500 focus:border-indigo-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md",
                                ),
                            ),
                        ),
                        d.Div(classes="mt-6")(
                            d.Button(
                                type="submit",
                                classes="inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                            )("Start Processing"),
                        ),
                    ),
                ),
            ),
            
            d.Div(id="process-status", classes="mt-4"),
        )


class UploadQueuePartial(Component):
    """Partial for upload queue."""
    
    def __init__(self, jobs: List[UploadJob]):
        super().__init__()
        self.jobs = jobs
    
    def render(self):
        if not self.jobs:
            return d.Div(classes="px-4 py-5 sm:p-6 text-center text-gray-500")(
                "No files in queue."
            )
        
        return d.Ul(classes="divide-y divide-gray-200")(
            *[FileRowPartial(job) for job in self.jobs]
        )


class FileRowPartial(Component):
    """Partial for a single file row."""
    
    def __init__(self, job: UploadJob):
        super().__init__()
        self.job = job
    
    def render(self):
        status = self.job.status.value if isinstance(self.job.status, UploadStatus) else str(self.job.status)
        filename = self.job.filename
        file_id = self.job.id
        
        status_colors = {
            UploadStatus.QUEUED.value: "bg-blue-100 text-blue-800",
            UploadStatus.UPLOADING.value: "bg-yellow-100 text-yellow-800",
            UploadStatus.PROCESSING.value: "bg-purple-100 text-purple-800",
            UploadStatus.DONE.value: "bg-green-100 text-green-800",
            UploadStatus.ERROR.value: "bg-red-100 text-red-800",
        }
        status_class = status_colors.get(status, "bg-gray-100 text-gray-800")
        
        return d.Li(classes="px-4 py-4 sm:px-6 flex items-center justify-between")(
            d.Div(classes="flex items-center")(
                d.Div(classes="flex-shrink-0 h-10 w-10 rounded-full bg-gray-200 flex items-center justify-center text-gray-500")(
                    "🎵"
                ),
                d.Div(classes="ml-4")(
                    d.Div(classes="text-sm font-medium text-gray-900")(filename),
                    d.Div(classes="text-sm text-gray-500")(
                        d.Span(classes=f"inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium {status_class}")(
                            status.capitalize()
                        )
                    ),
                ),
            ),
            d.Div(classes="flex items-center space-x-4")(
                # Progress bar if processing
                UploadProgressPartial(file_id, self.job.progress) if status in [UploadStatus.PROCESSING.value, UploadStatus.UPLOADING.value] else None,
                d.Button(
                    classes="text-red-600 hover:text-red-900 text-sm font-medium",
                    hx_delete=f"/upload/files/{file_id}",
                    hx_target="closest li",
                    hx_swap="outerHTML",
                )("Remove"),
            ),
        )


class UploadProgressPartial(Component):
    """Partial for upload/processing progress."""
    
    def __init__(self, job_id: str, progress: float):
        super().__init__()
        self.job_id = job_id
        self.progress = progress
    
    def render(self):
        return d.Div(
            hx_ext="sse",
            sse_connect=f"/upload/progress/{self.job_id}",
            sse_swap="message",
            classes="w-32"
        )(
            d.Div(classes="w-full bg-gray-200 rounded-full h-2.5")(
                d.Div(
                    classes="bg-indigo-600 h-2.5 rounded-full transition-all duration-300",
                    style=f"width: {self.progress}%"
                )
            )
        )
