using System;
using UnityEngine;
using UnityEngine.UI;

[RequireComponent(typeof(Dropdown))]
public class ColormapDropdown : MonoBehaviour
{
    [SerializeField] private Image previewImage;
    private Dropdown dropdown;

    private void Awake()
    {
        dropdown = GetComponent<Dropdown>();
    }

    public void SetPreview(Int32 index)
    {
        previewImage.sprite = GetComponent<Dropdown>().options[index].image;
    }
    
    public void ChangeColormap(Int32 id)
    {
        Texture2D tex = dropdown.options[id].image.texture;
        GameManager.instance.ApplyColormap(tex);
    }
}
