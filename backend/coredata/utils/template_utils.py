import os
from django.conf import settings
from django.template.loaders.filesystem import Loader as FilesystemLoader
from django.template.loaders.app_directories import Loader as AppDirectoriesLoader

class PersonalizedTemplateLoaderMixin:
    def get_template_sources(self, template_name, *args, **kwargs):
        # If the template_name is not already personalized and is an HTML file
        if template_name.endswith('.html') and not template_name.endswith('_personalized.html'):
            base, ext = os.path.splitext(template_name)
            personalized_name = f"{base}_personalized{ext}"
            for source in super().get_template_sources(personalized_name, *args, **kwargs):
                yield source
        
        # Yield original template name as fallback
        for source in super().get_template_sources(template_name, *args, **kwargs):
            yield source


class PersonalizedFilesystemLoader(PersonalizedTemplateLoaderMixin, FilesystemLoader):
    pass

class PersonalizedAppDirectoriesLoader(PersonalizedTemplateLoaderMixin, AppDirectoriesLoader):
    pass

def build_template_candidates(default_rel_path, lang=None):
    """
    Builds the ordered list of template name candidates to try, in order of priority:
      1. personalized + language variant (e.g. 'invoice_template_personalized_es.html')
      2. language variant (e.g. 'invoice_template_es.html')
      3. personalized variant (e.g. 'invoice_template_personalized.html')
      4. default path
    Shared by resolve_template_path() (which picks the first one that exists on disk,
    for callers that open the file directly) and callers that pass the whole list to
    Django's render_to_string()/template loaders and let them resolve it.
    """
    if not default_rel_path:
        return [default_rel_path]

    base, ext = os.path.splitext(default_rel_path)

    candidates = []
    if lang:
        candidates.append(f"{base}_personalized_{lang}{ext}")
        candidates.append(f"{base}_{lang}{ext}")
    candidates.append(f"{base}_personalized{ext}")
    candidates.append(default_rel_path)
    return candidates


def resolve_template_path(default_rel_path, lang=None):
    """
    Resolves the template path to use (see build_template_candidates() for the
    priority order). Each candidate is only used if it actually exists on disk;
    otherwise falls back to the next one down to the default path.
    """
    if not default_rel_path:
        return default_rel_path

    for candidate in build_template_candidates(default_rel_path, lang=lang):
        abs_candidate = candidate if os.path.isabs(candidate) else os.path.join(settings.BASE_DIR, candidate)
        if os.path.exists(abs_candidate):
            return abs_candidate

    if os.path.isabs(default_rel_path):
        return default_rel_path
    return os.path.join(settings.BASE_DIR, default_rel_path)
