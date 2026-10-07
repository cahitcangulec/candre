from resources.lib.common import source_utils
from resources.lib.debrid.real_debrid import RealDebrid
from resources.lib.modules.exceptions import TorrentNotCached
from resources.lib.modules.globals import g
from resources.lib.modules.resolver.torrent_resolvers.base_resolver import (
    TorrentResolverBase,
)


class RealDebridResolver(TorrentResolverBase):
    """
    Resolver for Real Debrid
    """

    def __init__(self):
        super().__init__()
        self.debrid_module = RealDebrid()
        self.torrent_id = None
        self._source_normalization = (
            ("path", "path", None),
            ("bytes", "size", lambda k: (k / 1024) / 1024),
            ("size", "size", None),
            ("filename", "release_title", None),
            ("id", "id", None),
            ("link", "link", None),
            ("selected", "selected", None),
        )

    def _files_for_picker(self, torrent_info):
        all_files = torrent_info.get("files") or []
        links = torrent_info.get("links") or []
        result = []
        for idx, file in enumerate(all_files):
            path = file.get("path") or ""
            if "sample" in path.lower() or not source_utils.is_file_ext_valid(path):
                continue
            if not self.pack_select and not file.get("selected"):
                continue
            item = dict(file)
            if idx < len(links) and links[idx]:
                item["link"] = links[idx]
            result.append(item)
        return result

    def resolve_magnet(self, item_information, torrent, pack_select=False):
        try:
            return super().resolve_magnet(item_information, torrent, pack_select)
        except Exception:
            # The probe keeps a cached torrent until its link is unrestricted: do not leave it in the
            # account when resolving fails before post-processing ran (no movie match, cancelled pick).
            self._delete_torrent(torrent)
            raise

    def _fetch_source_files(self, torrent, item_information):
        # Raises TorrentNotCached when RD does not report the torrent "downloaded": the resolver then
        # skips this source silently and tries the next one.
        try:
            hash_check = self.debrid_module.check_hash(torrent["hash"], keep_torrent=True)
        except TorrentNotCached as e:
            if e.persist:
                self._store_probe_result(torrent["hash"], "False")
            raise
        entry = hash_check.get(torrent["hash"])
        if not entry:
            raise TorrentNotCached(torrent["hash"], "empty probe result", persist=False)

        self._store_probe_result(torrent["hash"], "True")
        self.torrent_id = entry["torrent_id"]
        torrent_info = entry["torrent_info"]
        if self.pack_select:
            self.debrid_module.torrent_select_all(self.torrent_id)
            torrent_info = self.debrid_module.torrent_info(self.torrent_id) or torrent_info
            if "files" in torrent_info:
                torrent_info["files"] = [
                    file
                    for file in torrent_info["files"]
                    if "sample" not in file.get("path", "").lower()
                    and source_utils.is_file_ext_valid(file.get("path", ""))
                ]

        return self._files_for_picker(torrent_info)

    def resolve_stream_url(self, file_info):
        """
        Convert provided source file into a link playable through debrid service
        :param file_info: Normalised information on source file
        :return: streamable link
        """
        return self.debrid_module.resolve_hoster(file_info["link"])

    @staticmethod
    def _store_probe_result(info_hash, cached):
        """
        Persist the resolve-time probe answer in the debrid cache, like a scrape-time check result:
        "True" (cached, 24 h) or "False" (not cached, 4 h), so the next scrape shows the truth.
        """
        try:
            from resources.lib.database.debridCache import DebridCache

            DebridCache().set_many([(info_hash, cached)], "rd")
        except Exception as e:
            g.log(f"Could not store the Real-Debrid probe result for {info_hash}: {e}", "warning")

    def _delete_torrent(self, torrent):
        if not self.torrent_id:
            return
        torrent_id, self.torrent_id = self.torrent_id, None
        # The file list holds this torrent's links: a later manual-selection retry must probe again
        # instead of unrestricting links of a deleted torrent.
        torrent.pop("_prism_cached_files", None)
        try:
            self.debrid_module.delete_torrent(torrent_id)
        except Exception as e:
            g.log(f"Could not delete Real-Debrid torrent {torrent_id}: {e}", "warning")

    def _do_post_processing(self, item_information, torrent, identified_file):
        # Runs after the link was unrestricted, or when no file matched. A failed resolve always
        # removes the torrent; a resolved one is kept only when rd.autodelete is off.
        if identified_file is None or g.get_bool_setting("rd.autodelete"):
            self._delete_torrent(torrent)
