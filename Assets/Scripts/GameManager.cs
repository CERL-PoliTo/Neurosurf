using System.Collections.Generic;
using UnityEngine;

public enum ModelLayerSelector
{
    Scalp,
    Skull,
    Brain,
    Fibers
}

public class GameManager : MonoBehaviour {
    public static GameManager instance = null;

    [Header("Model Layers")]
    [SerializeField] private GameObject scalp;
    [SerializeField] private GameObject skull;
    [SerializeField] private GameObject brain;
    [SerializeField] private GameObject fibers;
    
    [Header("LSL Stream Names")]
    [SerializeField] public string scalpStreamName = "ScalpSurface";
    [SerializeField] public string brainStreamName = "BrainSurface";
    [SerializeField] public string fiberStreamName = "fibersActivation";
    
    [Header("Layers Transparency")]
    [Range(0, 1)] public float transparencyValueScalp = 0.5F;
    [Range(0, 1)] public float transparencyValueSkull = 0.2F;
    [Range(0, 1)] public float transparencyValueBrain = 0.5F;

    [Header("Render Queues")]
    public int scalpRenderQueue = 5000;
    public int skullRenderQueue = 4500;
    public int brainRenderQueue = 4000;
    public int fiberRenderQueue = 3500;

    [Header("Shader Property Names")]
    [SerializeField] private string propertyAlphaScalp = "_Alpha";
    [SerializeField] private string propertyAlphaSkull = "_Alpha";
    [SerializeField] private string propertyAlphaBrain = "_Alpha";
    
    [Header("Materials and View Settings")]
    [SerializeField] private Material noStreamMaterialScalp;
    [SerializeField] private Material noStreamMaterialBrain;
    [SerializeField] private Material streamMaterialScalp;
    [SerializeField] private Material streamMaterialBrain;
    public bool perFrameNormalization;
    
    [Header("Performance")]
    [SerializeField, Min(0)] private int targetFrameRate = 0; // 0 for unlimited
    
    private ActivationSurface scalpMeshActivationSurface;
    private ActivationSurface brainMeshActivationSurface;

    private Dictionary<ModelLayerSelector, float> transparencyMap;
    private Dictionary<ModelLayerSelector, int> renderQueueMap;
    private Dictionary<ModelLayerSelector, string> propertyAlphaMap;


    void Awake()
    {
        if (instance == null)
            instance = this;
        else if (instance != this)
            Destroy(gameObject);
        DontDestroyOnLoad(gameObject);

        if (targetFrameRate != 0)
            Application.targetFrameRate = targetFrameRate;
        
        transparencyMap = new Dictionary<ModelLayerSelector, float>
        {
            { ModelLayerSelector.Scalp, transparencyValueScalp },
            { ModelLayerSelector.Skull, transparencyValueSkull },
            { ModelLayerSelector.Brain, transparencyValueBrain }
        };

        renderQueueMap = new Dictionary<ModelLayerSelector, int>
        {
            { ModelLayerSelector.Scalp, scalpRenderQueue },
            { ModelLayerSelector.Skull, skullRenderQueue },
            { ModelLayerSelector.Brain, brainRenderQueue },
            { ModelLayerSelector.Fibers, fiberRenderQueue }
        };

        propertyAlphaMap = new Dictionary<ModelLayerSelector, string>
        {
            { ModelLayerSelector.Scalp, propertyAlphaScalp },
            { ModelLayerSelector.Skull, propertyAlphaSkull },
            { ModelLayerSelector.Brain, propertyAlphaBrain }
        };
    }

    void Start()
    {
        scalpMeshActivationSurface = scalp.GetComponent<ActivationSurface>();
        brainMeshActivationSurface = brain.GetComponent<ActivationSurface>();
    }
    
    
    public float GetTransparencyValue(ModelLayerSelector selector)
    {
        return transparencyMap.GetValueOrDefault(selector, 0);
    }

    public int GetRenderQueue(ModelLayerSelector selector)
    {
        return renderQueueMap.GetValueOrDefault(selector, 0);
    }

    public string GetPropertyAlpha(ModelLayerSelector selector)
    {
        return propertyAlphaMap[selector];
    }

    public void SetTransparencyValue(ModelLayerSelector selector, float value)
    {
        if (transparencyMap.ContainsKey(selector))
            transparencyMap[selector] = value;

        switch (selector)
        {
            case ModelLayerSelector.Scalp: scalpMeshActivationSurface.SetShaderProperty(value); break;
            case ModelLayerSelector.Skull: skull.GetComponent<SkullMaterialController>().SetAlpha(value); break;
            case ModelLayerSelector.Brain: brainMeshActivationSurface.SetShaderProperty(value); break;
        }
    }
    
    public void SetScalpActive(bool isActive)    {
        scalp.SetActive(isActive);
    }
    
    public void SetSkullActive(bool isActive)    {
        skull.SetActive(isActive);
    }
    
    public void SetBrainActive(bool isActive)    {
        brain.SetActive(isActive);
    }
    
    public void SetFibersActive(bool isActive)    {
        fibers.SetActive(isActive);
    }

    public string GetLslStreamName(ModelLayerSelector objectSelector)
    {
        return objectSelector switch
        {
            ModelLayerSelector.Scalp => scalpStreamName,
            ModelLayerSelector.Brain => brainStreamName,
            ModelLayerSelector.Fibers => fiberStreamName,
            _ => ""
        };
    }

    public Material GetStreamMaterial(ModelLayerSelector objectSelector)
    {
        return objectSelector switch
        {
            ModelLayerSelector.Scalp => streamMaterialScalp,
            ModelLayerSelector.Brain => streamMaterialBrain,
            _ => null
        };
    }
    
    public Material GetNoStreamMaterial(ModelLayerSelector objectSelector)
    {
        return objectSelector switch
        {
            ModelLayerSelector.Scalp => noStreamMaterialScalp,
            ModelLayerSelector.Brain => noStreamMaterialBrain,
            _ => null
        };
    }
    
    public void ApplyColormap(Texture2D tex)
    {
        scalpMeshActivationSurface.SetShaderColormap(tex);
        brainMeshActivationSurface.SetShaderColormap(tex);
    }
    
    void OnApplicationQuit()
    {
        LslReceiver.ShutdownRequested = true;
        Debug.Log("Exiting the game");
    }
}
