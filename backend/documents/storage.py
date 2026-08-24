class DocumentStorageUnavailable(Exception):
    pass


def store_document(*args, **kwargs):
    raise DocumentStorageUnavailable("Binary document storage is not configured.")


def get_document_download_url(document):
    return document.external_url


def delete_document_blob(*args, **kwargs):
    raise DocumentStorageUnavailable("Physical deletion is deferred.")
