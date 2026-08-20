#if UNITY_EDITOR
using System.IO;
using UnityEditor;
using UnityEditor.PackageManager.UI;
using UnityEngine;
using TMPro;

[InitializeOnLoad]
public static class ImportPluginAssets
{
    // XR Interaction Toolkit
    private const string XriPackageName = "com.unity.xr.interaction.toolkit";
    private const string XriPackageVersion = "3.1.2";
    private static readonly string[] XriSamplesToImport =
    {
        "Starter Assets",
        "Hands Interaction Demo"
    };
    
    // XR Hands
    private const string XrhPackageName = "com.unity.xr.hands";
    private const string XrhPackageVersion = "1.5.1";
    private static readonly string[] XrhSamplesToImport = { "HandVisualizer" };

    private const string TmpResourcesPath = "Assets/TextMesh Pro/Resources";
    
    static ImportPluginAssets()
    {
        EditorApplication.delayCall += ImportAllAssets;
    }

    private static void ImportAllAssets()
    {
        ImportSample(XrhPackageName, XrhPackageVersion, XrhSamplesToImport);
        ImportSample(XriPackageName, XriPackageVersion, XriSamplesToImport);
        
        if (!Directory.Exists(TmpResourcesPath))
        {
            Debug.Log("[TMPAutoImport] TMP resources not found. Importing Essential Resources...");
            ImportTMPEssentials();
        }
    }
    
    private static void ImportSample(string packageName, string packageVersion, string[] samplesToImport)
    {
        var samples = Sample.FindByPackage(packageName, packageVersion);
        foreach (Sample sample in samples)
        {
            if (!System.Array.Exists(samplesToImport, name => name == sample.displayName)) continue;
            if (sample.isImported) continue;
            sample.Import();
            Debug.Log($"Imported sample: {sample.displayName}");
        }
    }
    
    private static void ImportTMPEssentials()
    {
        TMP_PackageResourceImporter.ImportResources(
            importEssentials: true,
            importExamples:   false,
            interactive:      false
        );

        Debug.Log("Imported TMP Essential Resources");
    }
}
#endif