#if UNITY_EDITOR
using System.IO;
using System.IO.Compression;
using System.Net.Http;
using System.Threading.Tasks;
using UnityEditor;
using UnityEngine;

public static class SampleAssetsBootstrap
{
    private const string SampleAssetsName = "SampleAssets_v01";
    private const string AssetsZipUrl =
        "https://github.com/CERL-PoliTo/Neurosurf/releases/download/v1.0.0/" + SampleAssetsName + ".zip";

    private static readonly string ProjectRoot =
        Directory.GetParent(Application.dataPath).FullName;

    private static readonly string MarkerFile =
        Path.Combine(ProjectRoot, "PhysicalModels", ".fibers_installed");
    
    static SampleAssetsBootstrap()
    {
        EditorApplication.update += OnEditorUpdateOnce;
    }

    private static void OnEditorUpdateOnce()
    {
        EditorApplication.update -= OnEditorUpdateOnce;
        
        if (Application.isBatchMode)
            return;
    
        if (!NeedAssets())
            return;
    
        Debug.LogWarning("Sample assets not found. Click 'Setup > Download Assets' to download and install them.");
    }
    
    private static bool NeedAssets()
    {
        return !File.Exists(MarkerFile);
    }

    private static async Task DownloadAndInstallAssets()
    {
        string tempZip = Path.Combine(Path.GetTempPath(), SampleAssetsName + ".zip");

        try
        {
            EditorUtility.DisplayProgressBar(
                "Downloading sample assets",
                "Connecting...",
                0f
            );

            using (var client = new HttpClient())
            using (var response = await client.GetAsync(AssetsZipUrl))
            {
                response.EnsureSuccessStatusCode();
                var bytes = await response.Content.ReadAsByteArrayAsync();
                File.WriteAllBytes(tempZip, bytes);
            }

            EditorUtility.DisplayProgressBar(
                "Installing sample assets",
                "Extracting files...",
                0.5f
            );
            
            ZipFile.ExtractToDirectory(tempZip, ProjectRoot, overwriteFiles: false);
            File.WriteAllText(MarkerFile, SampleAssetsName);

            EditorUtility.ClearProgressBar();
            EditorUtility.DisplayDialog(
                "Sample assets installed",
                "The fibers meshes and data files were downloaded and installed successfully.",
                "OK"
            );
            
            AssetDatabase.Refresh(); // need to update unity after the download
        }
        catch (System.Exception e)
        {
            EditorUtility.ClearProgressBar();
            Debug.LogError($"Error downloading/installing sample assets: {e}");
            EditorUtility.DisplayDialog(
                "Error",
                "Failed to download or unpack the sample assets.\n" +
                "Check the Console for details.",
                "OK"
            );
        }
        finally
        {
            if (File.Exists(tempZip))
                File.Delete(tempZip);
        }
    }
    
    [MenuItem("Setup/Download Assets")]
    private static void MenuDownloadAssets()
    {
        _ = DownloadAndInstallAssets();
    }
}
#endif
